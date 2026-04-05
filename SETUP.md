# Bizkaia Connectivity MVP — Setup Guide

Run this project on any machine (Mac, Linux, Windows with WSL) and get identical results.

## Prerequisites

- **Docker** + **Docker Compose** (v2)
- **Git**
- Optional: **Python 3.11+** (only needed if running outside Docker)
- Optional: **gcloud CLI** (only for GCP deployment)

## Quick Start (Docker — recommended)

```bash
# 1. Clone the repo
git clone <your-repo-url> bizkaia-connectivity
cd bizkaia-connectivity

# 2. Copy environment file
cp docker/.env.example docker/.env

# 3. Start everything (builds images + starts backend + frontend)
make up

# 4. Seed demo data (generates synthetic grid, destinations, scores)
make seed

# 5. Open the app
#    Frontend: http://localhost:3000
#    API docs: http://localhost:8000/docs
```

The `make seed` command runs the full demo pipeline:
1. Creates tenants, modes, destination_types Parquet files
2. Creates a demo boundary over Bilbao
3. Generates a 250m grid (~576 cells)
4. Seeds 20 synthetic destinations (jobs, schools, health, supermarkets)
5. Generates distance-based travel times for 48 departure slots
6. Computes accessibility scores and combined scores

All output goes to `data/serving/*.parquet`. The backend loads these on startup.

## Quick Start (without Docker)

```bash
# 1. Clone
git clone <your-repo-url> bizkaia-connectivity
cd bizkaia-connectivity

# 2. Install backend dependencies
cd backend
python3.11 -m venv .venv
.venv/bin/pip install poetry==1.8.3
.venv/bin/poetry install
cd ..

# 3. Install worker dependencies
cd worker
python3.11 -m venv .venv
.venv/bin/pip install poetry==1.8.3
.venv/bin/poetry install
cd ..

# 4. Install frontend dependencies
cd frontend
npm install -g pnpm
pnpm install
cd ..

# 5. Seed demo data
mkdir -p data/serving
PYTHONPATH=worker/src SERVING_DIR=./data/serving \
  worker/.venv/bin/python -m worker.cli seed-demo --serving-dir ./data/serving

# 6. Start the backend
PYTHONPATH=backend/src DATA_DIR=./data/serving ENVIRONMENT=local \
  backend/.venv/bin/uvicorn backend.main:app --port 8000 --reload &

# 7. Start the frontend
cd frontend && pnpm dev &

# 8. Open http://localhost:3000
```

## Using Real Data (GeoEuskadi)

To use real Bizkaia data instead of synthetic demo data:

```bash
# Import real boundaries, municipalities, destinations from GeoEuskadi
make import
# OR without Docker:
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-geoeuskadi --serving-dir ./data/serving

# Import population data (requires EUSTAT shapefiles in data/raw/)
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-population --serving-dir ./data/serving

# Import nucleos for dasymetric masking (requires EUSTAT shapefiles)
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-nucleos --serving-dir ./data/serving

# Build grid over real boundary
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli build-grid --serving-dir ./data/serving

# Disaggregate population
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli disaggregate-population --serving-dir ./data/serving

# After R5R routing (produces ttm_*.parquet in data/output/):
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli run-pipeline --serving-dir ./data/serving

# Import sociodemographic data
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-demographics --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-income --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-car-ownership --serving-dir ./data/serving

# Import GTFS transit data
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli download-gtfs
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli import-gtfs-shapes --serving-dir ./data/serving
PYTHONPATH=worker/src worker/.venv/bin/python -m worker.cli compute-frequency --serving-dir ./data/serving

# Reload backend (picks up new data without restart)
curl -X POST http://localhost:8000/admin/reload
```

## Deploy to Google Cloud

```bash
# 1. One-time GCP setup (bucket, service account, artifact registry)
bash infra/setup-gcp.sh

# 2. Upload data to GCS
make upload
# OR: gcloud storage cp data/serving/*.parquet gs://bizkaia-conn-data/serving/

# 3. Build and deploy to Cloud Run
bash infra/deploy.sh
```

**Estimated cost**: $5–15/month (Cloud Run scales to zero + GCS storage).

## Architecture

```
data/serving/*.parquet   ←  Worker pipeline (GeoPandas + DuckDB)
        ↓
   DuckDB (in-memory)    ←  Backend loads Parquet on startup
        ↓
   FastAPI REST API       ←  Same GeoJSON responses as before
        ↓
   React + Maplibre       ←  Frontend (unchanged)
```

- **No PostgreSQL or PostGIS needed** — everything runs on DuckDB (embedded, zero-config)
- Worker writes Parquet files → Backend reads them → Frontend calls the API
- For GCP: Parquet files live in Cloud Storage, backend runs on Cloud Run

## Key Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start backend + frontend (Docker) |
| `make seed` | Generate synthetic demo data |
| `make import` | Import real data from GeoEuskadi |
| `make pipeline` | Run full production pipeline |
| `make upload` | Upload serving data to GCS |
| `make reload` | Hot-reload backend data |
| `make logs` | Tail all logs |
| `make down` | Stop everything |
| `make help` | Show all commands |

## Verifying Results

After seeding, check:

```bash
# API health
curl http://localhost:8000/health

# Grid cells with scores
curl "http://localhost:8000/cells/geojson?departure_time=08:00" | python3 -m json.tool | head -20

# Dashboard summary
curl "http://localhost:8000/dashboard/summary?departure_time=08:00" | python3 -m json.tool

# Available departure times
curl http://localhost:8000/cells/departure-times
```

The seed data is deterministic — same inputs always produce the same Parquet files and scores.
