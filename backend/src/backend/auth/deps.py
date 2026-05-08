"""FastAPI authentication and tenant dependencies."""

import time
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
import jwt
from jwt import PyJWTError

from backend.auth.schemas import MAX_TOKEN_TTL_SECONDS, TenantContext, TokenPayload
from backend.config import Settings, get_settings

_logger = structlog.stdlib.get_logger(__name__)

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def get_tenant(
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
    x_app_token: Annotated[str | None, Header(include_in_schema=False)] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> TenantContext:
    """Extract tenant context from JWT or dev header.

    When the Vercel proxy is in front of Cloud Run, Cloud Run IAM consumes the
    Authorization header (Google ID token). The proxy moves the user's app JWT
    to X-App-Token so we check that first, then fall back to Authorization.
    """
    if settings.environment == "local":
        tenant_id = x_tenant_id or DEMO_TENANT_ID
        ctx = TenantContext(tenant_id=tenant_id, user_id="dev-user", role="admin")
        _bind_log_context(ctx)
        return ctx

    # Prefer X-App-Token (set by the Vercel proxy); fall back to direct Authorization.
    raw_token = x_app_token or authorization
    if not raw_token or not raw_token.startswith("Bearer "):
        # Public tool: unauthenticated requests get read-only access to the demo tenant.
        ctx = TenantContext(tenant_id=DEMO_TENANT_ID, user_id="anonymous", role="viewer")
        _bind_log_context(ctx)
        return ctx

    token = raw_token.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        token_data = TokenPayload(**payload)
    except (PyJWTError, ValueError) as exc:
        _logger.warning("auth.invalid_token", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    # Reject tokens with unreasonably long TTL
    now = int(time.time())
    if token_data.exp - now > MAX_TOKEN_TTL_SECONDS:
        _logger.warning(
            "auth.ttl_exceeded",
            max_ttl_seconds=MAX_TOKEN_TTL_SECONDS,
            user_id=token_data.sub,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token lifetime exceeds maximum allowed",
        )

    ctx = TenantContext(
        tenant_id=token_data.tenant_id,
        user_id=token_data.sub,
        role=token_data.role,
    )
    _bind_log_context(ctx)
    _logger.debug("auth.success")
    return ctx


def _bind_log_context(ctx: TenantContext) -> None:
    """Add tenant_id, user_id, role to structlog context for the rest of the request."""
    structlog.contextvars.bind_contextvars(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        role=ctx.role,
    )
