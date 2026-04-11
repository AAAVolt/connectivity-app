"""FastAPI authentication and tenant dependencies."""

import logging
import time

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from backend.auth.schemas import MAX_TOKEN_TTL_SECONDS, TenantContext, TokenPayload
from backend.config import Settings, get_settings

_logger = logging.getLogger(__name__)

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def get_tenant(
    authorization: str | None = Header(None, include_in_schema=False),
    x_tenant_id: str | None = Header(None),
    settings: Settings = Depends(get_settings),
) -> TenantContext:
    """Extract tenant context from JWT or dev header."""
    if settings.environment == "local":
        tenant_id = x_tenant_id or DEMO_TENANT_ID
        return TenantContext(tenant_id=tenant_id, user_id="dev-user", role="admin")

    if not authorization or not authorization.startswith("Bearer "):
        _logger.info("Auth failed: missing or malformed Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValueError) as exc:
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
