# Bizkaia Connectivity — Operations Runbook

This document is for the on-call engineer. Keep it short, concrete, and tested.

Project: `bizkaia-conn-pub` · Region: `europe-southwest1` · Service: `bizkaia-api`

---

## 1. Health checks

| Endpoint | Meaning | Used by |
|---|---|---|
| `GET /health` | Process is up and serving HTTP. Returns 200 always. | Cloud Run liveness |
| `GET /readiness` | DuckDB is loaded and Parquet schemas validated. 503 during cold start, 200 once ready. | Cloud Run startup probe |

Quick smoke from the laptop:
```bash
curl -fsS https://bizkaia-api-cos3esbs4a-no.a.run.app/readiness
curl -fsS "https://bizkaia-api-cos3esbs4a-no.a.run.app/cells/geojson?limit=10" | jq '.features | length'
```

---

## 2. Rolling out a deploy

The default `infra/deploy.sh` does a 100% cutover. For anything riskier than a one-line fix, deploy as a **no-traffic revision first**, verify, then split traffic.

### 2a. Standard cutover (low-risk changes)

```bash
bash infra/deploy.sh
```

This builds, pushes, and routes 100% of traffic to the new revision immediately.

### 2b. Canary (recommended for any change touching db.py / contracts.py / scoring)

Build and push a no-traffic revision:
```bash
gcloud run deploy bizkaia-api \
  --image=europe-southwest1-docker.pkg.dev/bizkaia-conn-pub/bizkaia-images/bizkaia-api:latest \
  --region=europe-southwest1 \
  --no-traffic \
  --tag=canary
```

Now the new revision is reachable at `https://canary---bizkaia-api-<hash>-no.a.run.app` but no production traffic flows to it. Test directly:
```bash
CANARY_URL=$(gcloud run services describe bizkaia-api --region=europe-southwest1 \
  --format='value(status.traffic[?(@.tag=="canary")].url)')
curl -fsS "${CANARY_URL}/readiness"
curl -fsS "${CANARY_URL}/cells/geojson?limit=10" | jq '.features | length'
```

Send 10% of real traffic:
```bash
gcloud run services update-traffic bizkaia-api --region=europe-southwest1 \
  --to-tags=canary=10
```

Watch for 5 minutes (see §4). If healthy, ramp to 50%, then 100%:
```bash
gcloud run services update-traffic bizkaia-api --region=europe-southwest1 --to-tags=canary=50
gcloud run services update-traffic bizkaia-api --region=europe-southwest1 --to-tags=canary=100
```

---

## 3. Rolling back

### 3a. Find the previous revision

```bash
gcloud run revisions list --service=bizkaia-api --region=europe-southwest1 \
  --format='table(name, active, createTime.date(), traffic.percent)' --limit=10
```

Look for the most recent revision that ran 100% traffic before the bad one.

### 3b. Flip traffic back

```bash
# Replace bizkaia-api-00042-abc with the known-good revision name from 3a.
gcloud run services update-traffic bizkaia-api --region=europe-southwest1 \
  --to-revisions=bizkaia-api-00042-abc=100
```

This is **instantaneous** — no rebuild, no image push, no cold start (the previous revision is kept warm by Cloud Run for at least 24 hours after losing traffic).

### 3c. Verify

```bash
curl -fsS https://bizkaia-api-cos3esbs4a-no.a.run.app/readiness
gcloud run services describe bizkaia-api --region=europe-southwest1 \
  --format='value(status.traffic)'
```

Then file a postmortem and revert the offending commit on `main` so the next deploy doesn't reintroduce the regression.

---

## 4. What to watch during a rollout

Until the Cloud Monitoring alert policies (see `docs/monitoring.md`) are wired to a notification channel, watch these by hand:

| Metric | Where | Threshold |
|---|---|---|
| 5xx rate | Cloud Run → Metrics → Request count by response code | < 1% |
| p95 latency | Cloud Run → Metrics → Request latency | < 2s |
| Container instance count | Cloud Run → Metrics → Container instance count | should plateau, not grow unbounded |
| Logs (errors) | Cloud Logging → `resource.type="cloud_run_revision" severity>=ERROR` | none new |

The `severity` field in error logs is set by the structured logging in `backend/logging.py`, so filtering by `severity=ERROR` gives clean signal.

---

## 5. Common incidents

### 5a. /readiness returns 503 forever

Most likely a schema-contract violation: the worker pushed Parquet that's missing a required column.

```bash
gcloud run logs read bizkaia-api --region=europe-southwest1 --limit=50 \
  --format='value(timestamp, severity, jsonPayload.message)' \
  | grep -E "contract\.violation|duckdb\.init"
```

If you see `contract.violation`, the offending column is in `issues=[...]`. Either:
- Roll back to the previous revision (§3) — that one was loading the previous Parquet successfully.
- Fix the worker output, re-upload to GCS, hit `/admin/reload` (admin JWT required).

### 5b. CORS errors from the frontend

The CORS regex was tightened in Wave 1; check the Cloud Run env var still matches the live frontend URL:

```bash
gcloud run services describe bizkaia-api --region=europe-southwest1 \
  --format='value(spec.template.spec.containers[0].env)' | tr ',' '\n' | grep CORS
```

If the frontend was redeployed under a new vercel.app subdomain that doesn't match `frontend-[a-z0-9-]+\.vercel\.app`, update `CORS_ORIGIN_REGEX` in `infra/deploy.sh` and redeploy.

### 5c. /tmp filling up

Should not happen since Wave 2 added `_cleanup_gcs_tmp_dir()` in `backend/db.py`, but if it ever does:
```bash
gcloud run services update bizkaia-api --region=europe-southwest1 --no-traffic
# Container restart drops /tmp.
```

---

## 6. Rotating the JWT secret

```bash
openssl rand -base64 32 | tr -d '\n' | \
  gcloud secrets versions add bizkaia-jwt-secret --project=bizkaia-conn-pub --data-file=-
# Force a new revision so the new version is mounted.
bash infra/deploy.sh
```

Existing tokens issued under the old secret will fail validation immediately. Public read access (no token) keeps working.

---

## 7. Restoring deleted GCS data

Versioning + 30-day soft-delete is enabled (Wave 1). To recover an accidentally-deleted Parquet file:

```bash
# List soft-deleted objects
gcloud storage ls --soft-deleted gs://bizkaia-data-pub/serving/

# Restore (replace <generation> with the soft-deleted generation number)
gcloud storage restore gs://bizkaia-data-pub/serving/grid_cells.parquet#<generation>
```

After restoration, hit `POST /admin/reload` so the running container picks up the recovered file.
