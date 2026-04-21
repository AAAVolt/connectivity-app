# Bizkaia Connectivity – Deployment Reference

## Data — Google Cloud Storage

**Bucket:** `gs://bizkaia-data-pub`
**Region:** `europe-southwest1` (Madrid)
**GCP project:** `bizkaia-conn-pub` (account: `alessandro.voltan@gmail.com`)

All analytics data is stored as Parquet files in `gs://bizkaia-data-pub/serving/`:

| File | Contents |
|---|---|
| `grid_cells.parquet` | 250 m grid cells with population |
| `connectivity_scores.parquet` | Per-cell scores by mode/purpose |
| `combined_scores.parquet` | Aggregate scores per cell |
| `min_travel_times.parquet` | Travel times from cells to destinations |
| `destinations.parquet` + `destination_types.parquet` | Jobs, schools, GPs, supermarkets |
| `municipalities.parquet` + `boundaries.parquet` | Admin boundaries (GeoJSON) |
| `comarcas.parquet` + `nucleos.parquet` | Sub-regions |
| `gtfs_stops.parquet` + `gtfs_routes.parquet` + `stop_frequency.parquet` | Transit network |
| `municipality_demographics.parquet` | Population by age group |
| `municipality_income.parquet` | Income indicators |
| `municipality_car_ownership.parquet` | Vehicles per inhabitant |
| `tenants.parquet` + `modes.parquet` + `population_sources.parquet` | Reference tables |

`gs://bizkaia-data-pub/raw/` holds raw input data (not served by the API).

There is no database. DuckDB reads directly from these Parquet files into memory at startup.

---

## API — Google Cloud Run

**Service:** `bizkaia-api`
**URL:** `https://bizkaia-api-cos3esbs4a-no.a.run.app`
**Project:** `bizkaia-conn-pub` | **Region:** `europe-southwest1`

At startup, Cloud Run downloads all Parquet files from GCS into DuckDB (in-process). No PostGIS, no persistent DB.

| Setting | Value |
|---|---|
| Memory | 2 GB |
| CPU | 1 vCPU |
| Min instances | 0 (scales to zero when idle) |
| Max instances | 5 |
| Timeout | 120 s |
| Auth | Public (`allUsers` invoker) |
| `DATA_SOURCE` | `gcs` |
| `GCS_BUCKET` | `bizkaia-data-pub` |
| `GCS_PREFIX` | `serving` |
| `ENVIRONMENT` | `production` |
| `CORS_ORIGIN_REGEX` | `https://.*\.(run\.app\|vercel\.app)` |
| `JWT_SECRET` | Secret Manager → `bizkaia-jwt-secret` |

Docker images are stored in Artifact Registry:
`europe-southwest1-docker.pkg.dev/bizkaia-conn-pub/bizkaia-images/bizkaia-api`

---

## Frontend — Vercel

**Project:** `frontend` (team: `alessandrovoltan-4656s-projects`)
**Production URL:** `https://frontend-eight-beige-18.vercel.app`

| Env var | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `/api/backend` |
| `BACKEND_CLOUD_RUN_URL` | `https://bizkaia-api-cos3esbs4a-no.a.run.app` |

The browser never calls Cloud Run directly. All API calls go through the Next.js server-side proxy at `/api/backend/[...path]`, which forwards them to Cloud Run. This keeps the backend URL out of the browser.

---

## Auth flow

```
Browser → /api/backend/<endpoint>
         → Vercel proxy (server-side, Next.js route handler)
           → Cloud Run /<endpoint>
             → No JWT         → anonymous viewer (public read access)
             → Valid JWT      → authenticated user with their role
             → Invalid JWT    → 401
```

The `/admin/reload` endpoint requires a JWT with `role: admin`.

---

## Common operations

### Update serving data
```bash
gcloud storage cp data/serving/*.parquet gs://bizkaia-data-pub/serving/

# Hot-reload without redeploying (requires admin JWT):
curl -X POST https://bizkaia-api-cos3esbs4a-no.a.run.app/admin/reload \
  -H "Authorization: Bearer <admin-jwt>"
```

### Redeploy the backend
```bash
bash infra/deploy.sh
```

### Redeploy the frontend
```bash
cd frontend && vercel --prod
```

### One-time GCP setup (already done)
```bash
bash infra/setup-gcp.sh
```

---

## Code repository

`github.com/AAAVolt/connectivity-app`

| Folder | Contents |
|---|---|
| `backend/` | FastAPI app (Python 3.11) |
| `frontend/` | Next.js + MapLibre (TypeScript) |
| `worker/` | Batch pipeline for data ingestion and scoring |
| `r5r/` | R + r5r routing scripts |
| `infra/` | `setup-gcp.sh`, `deploy.sh` |
| `docker/` | Dockerfiles |
| `docs/` | Architecture notes and runbooks |
