"""Bizkaia Connectivity MVP – FastAPI backend."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
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
from backend.db import close_db, init_db, reload_db
from backend.logging import configure_logging, get_logger

# Configure structured logging once, before any module-level loggers are
# created. Subsequent get_logger() calls pick up the configured chain.
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "duckdb.loading",
        data_dir=settings.data_dir,
        data_source=settings.data_source,
    )
    init_db(settings)
    try:
        yield
    finally:
        # Cloud Run sends SIGTERM with a short grace period; release DuckDB
        # cleanly and remove any GCS temp directory we created so the next
        # cold-start container doesn't inherit stale state on reuse.
        logger.info("shutdown.start")
        close_db()
        logger.info("shutdown.done")


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
    async def request_context_and_security(request: Request, call_next):  # type: ignore[type-arg]
        # Bind request_id (and any inbound trace id) to the structlog
        # context so every log line emitted while handling this request
        # carries it. clear_contextvars at the end prevents leakage across
        # requests served on the same worker.
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response: Response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
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
        logger.info("admin.reload_triggered")
        reload_db()
        # Invalidate all server-side result caches after data reload
        from backend.api.cache import clear_all as clear_result_cache
        clear_result_cache()
        return {"status": "reloaded"}

    return application


app = create_app()
