# Bizkaia Connectivity MVP — local development commands (DuckDB)
# Usage: make <target>

COMPOSE := docker compose -f docker-compose.local.yml

.PHONY: up down build logs restart \
        backend-shell worker-shell \
        test test-backend test-frontend \
        seed routing upload clean

# ── Lifecycle ───────────────────────────────────────────

up:              ## Start all services (backend, frontend)
	$(COMPOSE) up -d --build
	@echo "\n  ✔ App running:"
	@echo "    Frontend → http://localhost:3000"
	@echo "    Backend  → http://localhost:8000"
	@echo "    API docs → http://localhost:8000/docs\n"

down:            ## Stop and remove containers
	$(COMPOSE) down

restart:         ## Restart all services
	$(COMPOSE) restart

build:           ## Rebuild images without starting
	$(COMPOSE) build

logs:            ## Tail logs (all services)
	$(COMPOSE) logs -f

logs-%:          ## Tail logs for one service, e.g. make logs-backend
	$(COMPOSE) logs -f $*

# ── Shells ──────────────────────────────────────────────

backend-shell:   ## Open a shell in the backend container
	$(COMPOSE) exec backend bash

worker-shell:    ## Open a shell in the worker container
	$(COMPOSE) exec worker bash

# ── Tests ��──────────────────────────────────────────────

test: test-backend test-frontend   ## Run all tests

test-backend:    ## Run backend pytest suite
	$(COMPOSE) exec backend python -m pytest -v

test-frontend:   ## Run frontend vitest suite
	$(COMPOSE) exec frontend pnpm test --run

# ── Routing (r5r) ─────────────────────────────────────��

routing:         ## Run the r5r routing container (one-shot)
	$(COMPOSE) run --rm r5r

# ── Worker tasks ─���──────────────────────────────────��───

seed:            ## Run worker demo data pipeline
	$(COMPOSE) run --rm worker python -m worker.cli seed-demo

import:          ## Import real data from GeoEuskadi
	$(COMPOSE) run --rm worker python -m worker.cli import-geoeuskadi

pipeline:        ## Run full production pipeline
	$(COMPOSE) run --rm worker python -m worker.cli run-pipeline

# ── GCS Upload ──────────────────────────────────────────

upload:          ## Upload serving data to GCS
	$(COMPOSE) run --rm worker python -m worker.cli upload-gcs

reload:          ## Trigger backend to reload data from disk
	curl -s -X POST http://localhost:8000/admin/reload

# ── Cleanup ─────────────────────────────────────────────

clean:           ## Stop containers and remove built images
	$(COMPOSE) down --rmi local

# ── Help ────────────────────────────────────────────────

help:            ## Show this help
	@grep -E '^[a-zA-Z_%-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
