# Load tests

k6 scripts for the Bizkaia Connectivity API.

## Setup

```bash
brew install k6              # one-time
```

## Run

```bash
# Against a local backend
make up                      # starts the API on :8000
make loadtest                # ramps 0 → 5 → 25 → 50 VUs over ~3 min

# Against the live API
BASE_URL=https://bizkaia-api-cos3esbs4a-no.a.run.app k6 run loadtest/cells.js

# Against staging
BASE_URL=https://bizkaia-api-staging-<hash>-no.a.run.app k6 run loadtest/cells.js
```

## What it asserts

Thresholds fail the k6 run (non-zero exit) if violated, so this is safe to wire into CI on a schedule:

| Metric | Threshold |
|---|---|
| `http_req_failed` (overall) | < 1% |
| `http_req_duration` p95 (overall) | < 2 s |
| `cells_geojson_latency` p95 | < 3 s |
| `dashboard_summary_latency` p95 | < 1.5 s |

## When to use it

- **After tuning Cloud Run config** (memory, CPU, max-instances) — confirms the change actually helps.
- **Before re-opening ADR-001** (DuckDB connection pooling) — the lock contention claim only holds if a load test shows it. Run against prod or staging at >25 VUs and watch p95 climb non-linearly.
- **As a cron job** — schedule against staging to catch regressions before they reach prod.

## Caveats

- Don't run against prod with > 5 VUs without warning the team. The API is public-read but Cloud Run still costs money under sustained load.
- The thresholds are loose by design — they're set high enough to catch genuine regressions, not flake. Tighten only after a few baseline runs.
- The 50-VU peak roughly matches 5 Cloud Run instances × ~10 concurrent requests each. Adjust if `max-instances` changes.
