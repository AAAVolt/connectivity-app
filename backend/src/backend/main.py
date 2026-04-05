"""Bizkaia Connectivity MVP – FastAPI backend."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.boundaries import router as boundaries_router
from backend.api.cells import router as cells_router
from backend.api.dashboard import router as dashboard_router
from backend.api.destinations import router as destinations_router
from backend.api.health import router as health_router
from backend.api.stats import router as stats_router
from backend.api.sociodemographic import router as sociodemographic_router
from backend.api.transit import router as transit_router
from backend.config import get_settings
from backend.db import init_db, reload_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("Loading DuckDB from %s (%s)", settings.data_dir, settings.data_source)
    init_db(settings)
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Bizkaia Connectivity API",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://*.run.app",       # Cloud Run frontend
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(boundaries_router)
    application.include_router(cells_router)
    application.include_router(dashboard_router)
    application.include_router(destinations_router)
    application.include_router(sociodemographic_router)
    application.include_router(stats_router)
    application.include_router(transit_router)

    # Admin endpoint to hot-reload data from GCS
    @application.post("/admin/reload", tags=["admin"])
    def admin_reload() -> dict[str, str]:
        reload_db()
        return {"status": "reloaded"}

    return application


app = create_app()
