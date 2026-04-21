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
async def test_missing_auth_header_returns_anonymous_viewer() -> None:
    """Public tool: no auth header → anonymous viewer on demo tenant."""
    settings = _prod_settings()

    ctx = get_tenant(authorization=None, x_app_token=None, x_tenant_id=None, settings=settings)
    assert ctx.user_id == "anonymous"
    assert ctx.role == "viewer"
    assert ctx.tenant_id == DEMO_TENANT_ID


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


# -- Missing / malformed claims ------------------------------------------------


@pytest.mark.asyncio
async def test_missing_tenant_id_claim_rejected() -> None:
    """Token without required 'tenant_id' claim should be rejected."""
    settings = _prod_settings()
    token = jwt.encode(
        {"sub": "user-1", "exp": int(time.time()) + 3600},
        SECRET,
        algorithm=ALGORITHM,
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            settings=settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_sub_claim_rejected() -> None:
    """Token without required 'sub' claim should be rejected."""
    settings = _prod_settings()
    token = jwt.encode(
        {"tenant_id": "tenant-1", "exp": int(time.time()) + 3600},
        SECRET,
        algorithm=ALGORITHM,
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        get_tenant(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            settings=settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_non_bearer_scheme_treated_as_anonymous() -> None:
    """An unrecognised auth scheme is ignored; falls back to anonymous viewer."""
    settings = _prod_settings()
    token = _make_token()

    ctx = get_tenant(
        authorization=f"Token {token}",
        x_app_token=None,
        x_tenant_id=None,
        settings=settings,
    )
    assert ctx.user_id == "anonymous"
    assert ctx.role == "viewer"


# -- Local dev mode details ----------------------------------------------------


@pytest.mark.asyncio
async def test_local_mode_custom_tenant_header() -> None:
    """In local mode, X-Tenant-ID header overrides the default demo tenant."""
    settings = Settings(environment="local")
    ctx = get_tenant(
        authorization=None,
        x_tenant_id="custom-tenant-999",
        settings=settings,
    )
    assert ctx.tenant_id == "custom-tenant-999"
    assert ctx.user_id == "dev-user"
    assert ctx.role == "admin"


@pytest.mark.asyncio
async def test_local_mode_default_demo_tenant() -> None:
    """In local mode without X-Tenant-ID, the demo tenant is used."""
    settings = Settings(environment="local")
    ctx = get_tenant(
        authorization=None,
        x_tenant_id=None,
        settings=settings,
    )
    assert ctx.tenant_id == DEMO_TENANT_ID
    assert ctx.role == "admin"


# -- Role extraction -----------------------------------------------------------


@pytest.mark.asyncio
async def test_role_extracted_from_token() -> None:
    """Token role claim should be reflected in the TenantContext."""
    settings = _prod_settings()
    token = _make_token(role="admin")

    ctx = get_tenant(
        authorization=f"Bearer {token}",
        x_tenant_id=None,
        settings=settings,
    )
    assert ctx.role == "admin"


@pytest.mark.asyncio
async def test_default_role_is_viewer() -> None:
    """Token without explicit role should default to 'viewer'."""
    settings = _prod_settings()
    payload = {
        "sub": "user-1",
        "tenant_id": "tenant-1",
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)

    ctx = get_tenant(
        authorization=f"Bearer {token}",
        x_tenant_id=None,
        settings=settings,
    )
    assert ctx.role == "viewer"


# -- Admin endpoint integration ------------------------------------------------


@pytest.mark.asyncio
async def test_admin_reload_forbidden_for_viewer() -> None:
    """POST /admin/reload should return 403 for non-admin users."""
    from unittest.mock import MagicMock
    from backend.db import get_db
    from backend.config import get_settings

    mock_session = MagicMock()
    app.dependency_overrides[get_settings] = lambda: _prod_settings()
    app.dependency_overrides[get_db] = lambda: (yield mock_session)

    try:
        token = _make_token(role="viewer")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/admin/reload",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# -- Config validation ---------------------------------------------------------


def test_insecure_secret_rejected_in_prod() -> None:
    """Settings should reject known-insecure secrets in non-local environments."""
    with pytest.raises(ValueError, match="JWT_SECRET must be set"):
        Settings(environment="production", jwt_secret="dev-secret-change-me")


def test_insecure_secret_allowed_in_local() -> None:
    """Insecure secrets are fine in local development."""
    settings = Settings(environment="local", jwt_secret="dev-secret-change-me")
    assert settings.jwt_secret == "dev-secret-change-me"
