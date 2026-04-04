# Bizkaia Connectivity MVP — local development commands
# Usage: make <target>

COMPOSE := docker compose -f docker-compose.local.yml

.PHONY: up down build logs restart \
        db-shell backend-shell worker-shell \
        test test-backend test-frontend \
        seed routing clean

# ── Lifecycle ───────────────────────────────────────────

up:              ## Start all services (db, backend, frontend)
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

# ── Database ────────────────────────────────────────────

db-shell:        ## Open psql in the database container
	$(COMPOSE) exec db psql -U bizkaia -d bizkaia

db-reset:        ## Destroy and recreate the database volume
	$(COMPOSE) down -v
	$(COMPOSE) up -d db
	@echo "  ✔ Database volume wiped and db restarted"

# ── Shells ──────────────────────────────────────────────

backend-shell:   ## Open a shell in the backend container
	$(COMPOSE) exec backend bash

worker-shell:    ## Open a shell in the worker container
	$(COMPOSE) exec worker bash

# ── Tests ───────────────────────────────────────────────

test: test-backend test-frontend   ## Run all tests

test-backend:    ## Run backend pytest suite
	$(COMPOSE) exec backend python -m pytest -v

test-frontend:   ## Run frontend vitest suite
	$(COMPOSE) exec frontend pnpm test --run

# ── Routing (r5r) ──────────────────────────────────────

routing:         ## Run the r5r routing container (one-shot)
	$(COMPOSE) run --rm r5r

# ── Worker tasks ────────────────────────────────────────

seed:            ## Run worker data ingestion pipeline
	$(COMPOSE) run --rm worker python -m worker.cli ingest

# ── Cleanup ─────────────────────────────────────────────

clean:           ## Stop containers, remove volumes and built images
	$(COMPOSE) down -v --rmi local

# ── Help ────────────────────────────────────────────────

help:            ## Show this help
	@grep -E '^[a-zA-Z_%-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
