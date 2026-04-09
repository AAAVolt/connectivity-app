# Bizkaia Connectivity MVP

A DfT-inspired transport connectivity tool for **Bizkaia**. Computes accessibility scores on a 250m grid based on public transport travel times to everyday destinations (jobs, schools, health, supermarkets), exposed through a REST API and interactive web map.

```
Frontend (React + Maplibre)  →  Backend (FastAPI + DuckDB)  →  Parquet files
```

## Prerequisites

- **Docker** + **Docker Compose** v2
- **Git**
- **gcloud CLI** — for downloading data ([install](https://cloud.google.com/sdk/docs/install))

## Quick start (new machine)

```bash
# 1. Clone
git clone https://github.com/AAAVolt/connectivity-app.git
cd connectivity-app

# 2. Authenticate with Google Cloud
gcloud auth login
gcloud config set project bizkaia-492317

# 3. Download all data from GCS (~870 MB)
bash scripts/sync-data.sh pull

# 4. Start the app
make up
```

That's it. Open:
- **Frontend** — http://localhost:3000
- **API docs** — http://localhost:8000/docs

## Data sync

All data files (GTFS feeds, OSM network, travel time matrices, POIs, shapefiles) live in a GCS bucket and are **not** checked into git. Use the sync script to push/pull:

```bash
# Download data from GCS → local data/
bash scripts/sync-data.sh pull

# Upload local data/ → GCS (after generating new data)
bash scripts/sync-data.sh push
```

The script syncs these directories:

| Directory | Contents | Size |
|-----------|----------|------|
| `data/gtfs/` | GTFS feeds (Bilbobus, Bizkaibus, Metro, Euskotren, Renfe) | ~57 MB |
| `data/network/` | R5R network (OSM + GTFS + `network.dat`) | ~419 MB |
| `data/output/` | Travel time matrices from R5R (48 half-hour slots) | ~321 MB |
| `data/pois/` | Points of interest (jobs, schools, health, supermarkets) | ~64 KB |
| `data/processed/` | Processed travel times | ~35 MB |
| `data/raw/` | EUSTAT shapefiles (nucleos, secciones, population) | ~36 MB |
| `data/serving/` | Final Parquet files consumed by the backend | generated |

**GCS bucket:** `gs://bizkaia-conn-data` (project `bizkaia-492317`, region `europe-southwest1`)

## Make commands

| Command | Description |
|---------|-------------|
| `make up` | Build and start all services (backend + frontend) |
| `make down` | Stop and remove containers |
| `make restart` | Restart all services |
| `make build` | Rebuild Docker images without starting |
| `make logs` | Tail logs for all services |
| `make logs-backend` | Tail logs for backend only |
| `make test` | Run all tests (backend + frontend) |
| `make test-backend` | Run backend pytest suite |
| `make test-frontend` | Run frontend vitest suite |
| `make seed` | Generate synthetic demo data (no real data needed) |
| `make import` | Import real boundaries + destinations from GeoEuskadi |
| `make pipeline` | Run full production pipeline (scoring from travel times) |
| `make routing` | Run R5R routing container (one-shot) |
| `make upload` | Upload `data/serving/` to GCS |
| `make reload` | Hot-reload backend data (no restart needed) |
| `make backend-shell` | Open a shell in the backend container |
| `make worker-shell` | Open a shell in the worker container |
| `make clean` | Stop containers and remove built images |
| `make help` | Show all available commands |

## Architecture

```
data/raw/                    ← EUSTAT shapefiles, population CSVs
data/gtfs/                   ← GTFS feeds from transit operators
data/network/                ← R5R network (OSM + GTFS → network.dat)
     ↓
  R5R routing (R)            ← Computes travel time matrices
     ↓
data/output/                 ← 48 Parquet files (one per half-hour slot)
     ↓
  Worker pipeline (Python)   ← Scoring, aggregation, demographics
     ↓
data/serving/*.parquet       ← Final data consumed by backend
     ↓
  FastAPI + DuckDB           ← Loads Parquet in-memory, serves GeoJSON
     ↓
  React + Maplibre           ← Interactive map UI
```

**No PostgreSQL needed** — DuckDB loads Parquet files in-process (zero-config, embedded).

## Production pipeline (generating data from scratch)

If you need to regenerate all data (not just sync existing):

```bash
# 1. Import real boundaries, municipalities, destinations
make import

# 2. Import population + shapefiles (requires data/raw/)
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-population --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-nucleos --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli build-grid --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli disaggregate-population --serving-dir ./data/serving

# 3. Run R5R routing (produces travel time matrices in data/output/)
make routing

# 4. Run scoring pipeline
make pipeline

# 5. Import sociodemographic + GTFS layers
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-demographics --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-income --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-car-ownership --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-gtfs-shapes --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli compute-frequency --serving-dir ./data/serving

# 6. Upload new data to GCS (so other machines can pull it)
bash scripts/sync-data.sh push

# 7. Reload backend
make reload
```

## Deploy to Google Cloud

```bash
# One-time GCP setup (bucket, service account, artifact registry)
bash infra/setup-gcp.sh

# Upload serving data to GCS
make upload

# Build and deploy to Cloud Run
export JWT_SECRET=$(openssl rand -base64 32)
bash infra/deploy.sh
```

Estimated cost: **$5-15/month** (Cloud Run scales to zero + GCS storage).

## Verifying

```bash
# Health check
curl http://localhost:8000/health

# Grid cells with scores
curl "http://localhost:8000/cells/geojson?departure_time=08:00" | python3 -m json.tool | head -20

# Dashboard summary
curl "http://localhost:8000/dashboard/summary?departure_time=08:00" | python3 -m json.tool

# Available departure times
curl http://localhost:8000/cells/departure-times
```

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React, TypeScript, Vite, Maplibre GL |
| Backend | FastAPI, DuckDB, Python 3.11 |
| Worker | Python, GeoPandas, DuckDB |
| Routing | R, r5r (R5 engine) |
| Data | Parquet files (local or GCS) |
| Infra | Docker Compose (local), Cloud Run + GCS (prod) |
