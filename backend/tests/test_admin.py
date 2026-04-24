"""Tests for admin API key management and AUTH_MODE=api_key dependency."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

from httpx import AsyncClient


async def test_admin_endpoints_disabled_without_secret(client: AsyncClient) -> None:
    resp = await client.post("/admin/tenants/t1/keys")
    assert resp.status_code == 503


async def test_admin_create_key_wrong_secret(client: AsyncClient) -> None:
    with patch("app.api.v1.admin.settings") as mock_s:
        mock_s.ADMIN_SECRET = "correct-secret"
        resp = await client.post(
            "/admin/tenants/t1/keys",
            headers={"X-Admin-Secret": "wrong"},
        )
    assert resp.status_code == 401


async def test_admin_create_and_list_keys(client: AsyncClient) -> None:
    with patch("app.api.v1.admin.settings") as mock_s:
        mock_s.ADMIN_SECRET = "supersecret"
        create_resp = await client.post(
            "/admin/tenants/tenant-x/keys?label=ci",
            headers={"X-Admin-Secret": "supersecret"},
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["tenant_id"] == "tenant-x"
        assert data["label"] == "ci"
        assert "key" in data
        raw_key: str = data["key"]

        list_resp = await client.get(
            "/admin/tenants/tenant-x/keys",
            headers={"X-Admin-Secret": "supersecret"},
        )
        assert list_resp.status_code == 200
        keys = list_resp.json()
        assert len(keys) == 1
        assert keys[0]["is_active"] is True

    return raw_key  # type: ignore[return-value]


async def test_admin_revoke_key(client: AsyncClient) -> None:
    with patch("app.api.v1.admin.settings") as mock_s:
        mock_s.ADMIN_SECRET = "supersecret"
        create_resp = await client.post(
            "/admin/tenants/tenant-y/keys",
            headers={"X-Admin-Secret": "supersecret"},
        )
        key_id = create_resp.json()["id"]

        revoke_resp = await client.delete(
            f"/admin/tenants/tenant-y/keys/{key_id}",
            headers={"X-Admin-Secret": "supersecret"},
        )
        assert revoke_resp.status_code == 204

        list_resp = await client.get(
            "/admin/tenants/tenant-y/keys",
            headers={"X-Admin-Secret": "supersecret"},
        )
        assert list_resp.json()[0]["is_active"] is False


async def test_api_key_auth_mode_valid_key(client: AsyncClient, tmp_path: Path) -> None:
    """With AUTH_MODE=api_key, a valid hashed key grants access."""
    from app.api.dependencies import get_current_tenant
    from app.core.database import get_db
    from app.main import app
    from app.models import TenantAPIKey

    raw_key = "test-raw-key-12345"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # Seed the key directly via db_session (shares the test engine via _test_engine fixture)
    # We need a db session — use the app's overridden get_db via a direct DB call
    db_gen = app.dependency_overrides[get_db]()
    db = await db_gen.__anext__()
    try:
        db.add(TenantAPIKey(tenant_id="keyed-tenant", key_hash=key_hash, label="test"))
        await db.commit()
    finally:
        await db_gen.aclose()

    # Remove the tenant override so get_current_tenant runs the real auth logic
    original_override = app.dependency_overrides.pop(get_current_tenant, None)
    try:
        with patch("app.api.dependencies.settings") as mock_s:
            mock_s.AUTH_MODE = "api_key"
            resp = await client.post(
                "/workspaces",
                json={"name": "R", "root_path": str(tmp_path)},
                headers={"X-API-Key": raw_key},
            )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "keyed-tenant"
    finally:
        if original_override:
            app.dependency_overrides[get_current_tenant] = original_override


async def test_api_key_auth_mode_missing_key(client: AsyncClient, tmp_path: Path) -> None:
    """With AUTH_MODE=api_key, missing key → 401."""
    from app.api.dependencies import get_current_tenant
    from app.main import app

    original_override = app.dependency_overrides.pop(get_current_tenant, None)
    try:
        with patch("app.api.dependencies.settings") as mock_s:
            mock_s.AUTH_MODE = "api_key"
            resp = await client.post(
                "/workspaces",
                json={"name": "R", "root_path": str(tmp_path)},
            )
        assert resp.status_code == 401
    finally:
        if original_override:
            app.dependency_overrides[get_current_tenant] = original_override
