"""FastAPI authentication and tenant dependencies."""

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from backend.auth.schemas import TenantContext, TokenPayload
from backend.config import Settings, get_settings

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    return TenantContext(
        tenant_id=token_data.tenant_id,
        user_id=token_data.sub,
        role=token_data.role,
    )
