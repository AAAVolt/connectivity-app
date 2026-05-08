"""Liveness and readiness probes."""

from fastapi import APIRouter, Response, status

from backend.db import is_ready

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: the process is up and serving HTTP."""
    return {"status": "ok", "service": "bizkaia-backend"}


@router.get("/readiness")
async def readiness(response: Response) -> dict[str, str]:
    """Readiness probe: returns 200 only once DuckDB is loaded.

    Cold starts on Cloud Run can take several seconds while Parquet files
    download from GCS. Pointing the startup probe at this endpoint instead
    of /health prevents traffic from being routed to a half-initialized
    instance.
    """
    if not is_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "initializing", "service": "bizkaia-backend"}
    return {"status": "ready", "service": "bizkaia-backend"}
