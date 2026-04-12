"""Bizkaia Connectivity MVP – FastAPI backend."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from backend.api.ratelimit import RateLimitMiddleware
from backend.api.boundaries import router as boundaries_router
from backend.api.cells import router as cells_router
from backend.api.dashboard import router as dashboard_router
from backend.api.destinations import router as destinations_router
from backend.api.health import router as health_router
from backend.api.stats import router as stats_router
from backend.api.sociodemographic import router as sociodemographic_router
from backend.api.transit import router as transit_router
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
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

    settings = get_settings()
    application.add_middleware(RateLimitMiddleware, rate=60, window=60)
    application.add_middleware(GZipMiddleware, minimum_size=500)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Tenant-ID"],
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[type-arg]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Request ID for tracing
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response.headers["X-Request-ID"] = request_id
        return response

    application.include_router(health_router)
    application.include_router(boundaries_router)
    application.include_router(cells_router)
    application.include_router(dashboard_router)
    application.include_router(destinations_router)
    application.include_router(sociodemographic_router)
    application.include_router(stats_router)
    application.include_router(transit_router)

    # Admin endpoint to hot-reload data from GCS (requires admin role)
    @application.post("/admin/reload", tags=["admin"])
    def admin_reload(
        tenant: TenantContext = Depends(get_tenant),
    ) -> dict[str, str]:
        if tenant.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required",
            )
        logger.info("Admin reload triggered by user=%s tenant=%s", tenant.user_id, tenant.tenant_id)
        reload_db()
        # Invalidate all server-side result caches after data reload
        from backend.api.cache import clear_all as clear_result_cache
        clear_result_cache()
        return {"status": "reloaded"}

    return application


app = create_app()
