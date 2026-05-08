// k6 load test against the public Bizkaia Connectivity API.
//
// Usage:
//   BASE_URL=http://localhost:8000  k6 run loadtest/cells.js
//   BASE_URL=https://bizkaia-api-cos3esbs4a-no.a.run.app  k6 run loadtest/cells.js
//
// Thresholds fail the run with a non-zero exit code, so this is also a
// valid CI/cron task for catching latency regressions.
//
// What it exercises (weighted, weights roughly match real traffic shape):
//   /readiness            small, every iteration
//   /cells/geojson        large GeoJSON; the most expensive endpoint
//   /dashboard/summary    tabular aggregations; representative
//   /cells/departure-times  tiny, cached
//
// Stages ramp 0 → 5 → 25 → 50 VUs over ~3 min so the test surfaces both
// cold-start cost and steady-state contention. 50 VUs roughly matches what
// 5 Cloud Run instances would absorb at our per-instance budget.

import http from 'k6/http';
import { check, group } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

const cellsLatency = new Trend('cells_geojson_latency', true);
const dashboardLatency = new Trend('dashboard_summary_latency', true);

export const options = {
  thresholds: {
    // Top-level: total request error rate < 1%
    http_req_failed: ['rate<0.01'],
    // Top-level: 95th percentile under 2s end-to-end
    http_req_duration: ['p(95)<2000'],
    // Endpoint-specific: the heavy GeoJSON endpoint is allowed to be slower
    cells_geojson_latency: ['p(95)<3000'],
    dashboard_summary_latency: ['p(95)<1500'],
  },
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 25 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '15s',
    },
  },
};

export default function () {
  group('readiness', () => {
    const res = http.get(`${BASE_URL}/readiness`);
    check(res, {
      'readiness 200': (r) => r.status === 200,
    });
  });

  group('cells_geojson', () => {
    const url = `${BASE_URL}/cells/geojson?resolution=1000&departure_time=08:00&limit=20000`;
    const res = http.get(url);
    cellsLatency.add(res.timings.duration);
    check(res, {
      'cells 200': (r) => r.status === 200,
      'cells is geojson': (r) => r.headers['Content-Type']?.startsWith('application/geo+json'),
      'cells has features': (r) => r.body && r.body.includes('"FeatureCollection"'),
    });
  });

  group('dashboard_summary', () => {
    const res = http.get(`${BASE_URL}/dashboard/summary?departure_time=08:00`);
    dashboardLatency.add(res.timings.duration);
    check(res, {
      'dashboard 200': (r) => r.status === 200,
    });
  });

  group('departure_times', () => {
    const res = http.get(`${BASE_URL}/cells/departure-times`);
    check(res, {
      'departure-times 200': (r) => r.status === 200,
    });
  });
}
