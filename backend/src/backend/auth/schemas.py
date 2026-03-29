"""Auth-related Pydantic schemas."""

from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    exp: int | None = None


class TenantContext(BaseModel):
    tenant_id: str
    user_id: str
