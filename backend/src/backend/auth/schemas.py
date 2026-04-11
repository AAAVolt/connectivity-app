"""Auth-related Pydantic schemas."""

from pydantic import BaseModel, field_validator

# Maximum token lifetime: 24 hours (in seconds)
MAX_TOKEN_TTL_SECONDS = 86400


class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    role: str = "viewer"
    exp: int

    @field_validator("exp")
    @classmethod
    def _exp_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Token expiration (exp) must be a positive timestamp")
        return v


class TenantContext(BaseModel):
    tenant_id: str
    user_id: str
    role: str = "viewer"
