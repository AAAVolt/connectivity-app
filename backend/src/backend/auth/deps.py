"""FastAPI authentication and tenant dependencies."""

import logging
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
import jwt
from jwt import PyJWTError

from backend.auth.schemas import MAX_TOKEN_TTL_SECONDS, TenantContext, TokenPayload
from backend.config import Settings, get_settings

_logger = logging.getLogger(__name__)

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
        return TenantContext(tenant_id=tenant_id, user_id="dev-user", role="admin")

    # Prefer X-App-Token (set by the Vercel proxy); fall back to direct Authorization.
    raw_token = x_app_token or authorization
    if not raw_token or not raw_token.startswith("Bearer "):
        # Public tool: unauthenticated requests get read-only access to the demo tenant.
        return TenantContext(tenant_id=DEMO_TENANT_ID, user_id="anonymous", role="viewer")

    token = raw_token.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        token_data = TokenPayload(**payload)
    except (PyJWTError, ValueError) as exc:
        _logger.warning("Auth failed: invalid token — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    # Reject tokens with unreasonably long TTL
    now = int(time.time())
    if token_data.exp - now > MAX_TOKEN_TTL_SECONDS:
        _logger.warning(
            "Auth failed: token TTL exceeds maximum (%d s) for user=%s",
            MAX_TOKEN_TTL_SECONDS,
            token_data.sub,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token lifetime exceeds maximum allowed",
        )

    _logger.debug("Auth success: user=%s tenant=%s role=%s", token_data.sub, token_data.tenant_id, token_data.role)

    return TenantContext(
        tenant_id=token_data.tenant_id,
        user_id=token_data.sub,
        role=token_data.role,
    )
