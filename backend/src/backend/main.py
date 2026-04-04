"""Bizkaia Connectivity MVP – FastAPI backend."""

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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Bizkaia Connectivity API",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
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

    return application


app = create_app()
