"""Tests for authentication and tenant resolution."""

import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from backend.auth.deps import get_tenant, DEMO_TENANT_ID
from backend.auth.schemas import MAX_TOKEN_TTL_SECONDS
from backend.config import Settings
from backend.main import app

SECRET = "test-secret-key"
ALGORITHM = "HS256"


def _make_token(
    sub: str = "user-1",
    tenant_id: str = "tenant-1",
    role: str = "viewer",
    exp: int | None = None,
    secret: str = SECRET,
) -> str:
    if exp is None:
        exp = int(time.time()) + 3600
    return jwt.encode(
        {"sub": sub, "tenant_id": tenant_id, "role": role, "exp": exp},
        secret,
        algorithm=ALGORITHM,
    )


def _prod_settings(**overrides) -> Settings:
    defaults = {
        "environment": "production",
        "jwt_secret": SECRET,
        "jwt_algorithm": ALGORITHM,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# -- Local (dev) mode: auth bypassed -----------------------------------------


@pytest.mark.asyncio
async def test_local_mode_returns_demo_tenant() -> None:
    """In local mode, no token is needed; demo tenant is returned."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


# -- Production mode: JWT validated -------------------------------------------


@pytest.mark.asyncio
async def test_valid_token_accepted() -> None:
    settings = _prod_settings()
    token = _make_token()

    with patch("backend.auth.deps.get_settings", return_value=settings):
        from fastapi import Header

        ctx = get_tenant(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            settings=settings,
        )

    assert ctx.user_id == "user-1"
    assert ctx.tenant_id == "tenant-1"
    assert ctx.role == "viewer"


@pytest.mark.asyncio
async def test_missing_auth_header_rejected() -> None:
    settings = _prod_settings()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(authorization=None, x_tenant_id=None, settings=settings)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_rejected() -> None:
    settings = _prod_settings()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(
            authorization="Bearer invalid.token.here",
            x_tenant_id=None,
            settings=settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected() -> None:
    settings = _prod_settings()
    token = _make_token(exp=int(time.time()) - 3600)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            settings=settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_excessive_ttl_rejected() -> None:
    settings = _prod_settings()
    token = _make_token(exp=int(time.time()) + MAX_TOKEN_TTL_SECONDS + 7200)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            settings=settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_rejected() -> None:
    settings = _prod_settings()
    token = _make_token(secret="wrong-secret")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            settings=settings,
        )
    assert exc_info.value.status_code == 401
