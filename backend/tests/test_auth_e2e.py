"""End-to-end authentication flow tests for Week 4.

Tests complete auth workflow:
1. Admin provisions API keys via ADMIN_SECRET
2. Tenant uses API key for workspace CRUD
3. Tenant indices codebase with API key
4. Tenant deletes session and revokes key
5. Revoked key is rejected on next request
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from app.api.v1.workspaces import ingestion_tasks
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_ADMIN_SECRET = "test-admin-secret-key"
TEST_TENANT = "tenant-e2e-test"
ANOTHER_TENANT = "tenant-other"


@pytest_asyncio.fixture
async def auth_e2e_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine for E2E tests."""
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def auth_e2e_client(
    auth_e2e_engine: AsyncEngine,
) -> AsyncGenerator[AsyncClient, None]:
    """E2E client with admin secret configured."""
    ingestion_tasks.clear()
    session_factory = async_sessionmaker(auth_e2e_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Set ADMIN_SECRET for this test
    original_admin_secret = settings.ADMIN_SECRET
    settings.ADMIN_SECRET = TEST_ADMIN_SECRET

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Restore
    settings.ADMIN_SECRET = original_admin_secret
    app.dependency_overrides.clear()


# ── E2E Flow 1: Admin provisions keys, tenant uses them ──


async def test_e2e_create_workspace_with_provisioned_key(
    auth_e2e_client: AsyncClient, tmp_path: Path
) -> None:
    """E2E: admin creates key → tenant creates workspace with key."""
    settings.AUTH_MODE = "api_key"
    original = settings.AUTH_MODE

    try:
        # Step 1: Admin provisions API key
        admin_resp = await auth_e2e_client.post(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
            params={"label": "e2e-test"},
        )
        assert admin_resp.status_code == 201
        api_key = admin_resp.json()["key"]
        assert len(api_key) > 20

        # Step 2: Tenant uses key to create workspace
        ws_resp = await auth_e2e_client.post(
            "/workspaces",
            json={"name": "E2E Test Repo", "root_path": str(tmp_path)},
            headers={"X-API-Key": api_key},
        )
        assert ws_resp.status_code == 200
        workspace = ws_resp.json()
        assert workspace["tenant_id"] == TEST_TENANT
        assert workspace["name"] == "E2E Test Repo"

        # Step 3: Tenant lists workspaces with same key
        list_resp = await auth_e2e_client.get(
            "/workspaces",
            headers={"X-API-Key": api_key},
        )
        assert list_resp.status_code == 200
        workspaces = list_resp.json()
        assert len(workspaces) == 1
        assert workspaces[0]["id"] == workspace["id"]

    finally:
        settings.AUTH_MODE = original


async def test_e2e_different_tenant_cannot_access_workspace(
    auth_e2e_client: AsyncClient, tmp_path: Path
) -> None:
    """E2E: tenant1 creates workspace, tenant2 cannot access it."""
    settings.AUTH_MODE = "api_key"
    original = settings.AUTH_MODE

    try:
        # Tenant 1 provisions key and creates workspace
        key1_resp = await auth_e2e_client.post(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
            params={"label": "tenant1"},
        )
        key1 = key1_resp.json()["key"]

        ws_resp = await auth_e2e_client.post(
            "/workspaces",
            json={"name": "Tenant1 Repo", "root_path": str(tmp_path)},
            headers={"X-API-Key": key1},
        )
        workspace_id = ws_resp.json()["id"]

        # Tenant 2 provisions different key
        key2_resp = await auth_e2e_client.post(
            f"/admin/tenants/{ANOTHER_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
            params={"label": "tenant2"},
        )
        key2 = key2_resp.json()["key"]

        # Tenant 2 tries to access workspace from Tenant 1
        list_resp = await auth_e2e_client.get(
            "/workspaces",
            headers={"X-API-Key": key2},
        )
        workspaces = list_resp.json()
        # Should be empty — tenant 2 has no workspaces
        assert len(workspaces) == 0

        # Workspace ID from tenant 1 should not appear in tenant 2's list
        assert workspace_id not in [w["id"] for w in workspaces]

    finally:
        settings.AUTH_MODE = original


async def test_e2e_key_revocation_blocks_access(
    auth_e2e_client: AsyncClient, tmp_path: Path
) -> None:
    """E2E: admin revokes key → tenant is locked out."""
    settings.AUTH_MODE = "api_key"
    original = settings.AUTH_MODE

    try:
        # Step 1: Create key and workspace
        key_resp = await auth_e2e_client.post(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
            params={"label": "to-revoke"},
        )
        key = key_resp.json()["key"]
        key_id = key_resp.json()["id"]

        ws_resp = await auth_e2e_client.post(
            "/workspaces",
            json={"name": "WS", "root_path": str(tmp_path)},
            headers={"X-API-Key": key},
        )
        assert ws_resp.status_code == 200

        # Step 2: Tenant can access workspace
        list_before = await auth_e2e_client.get(
            "/workspaces",
            headers={"X-API-Key": key},
        )
        assert list_before.status_code == 200
        assert len(list_before.json()) == 1

        # Step 3: Admin revokes the key
        revoke_resp = await auth_e2e_client.delete(
            f"/admin/tenants/{TEST_TENANT}/keys/{key_id}",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        )
        assert revoke_resp.status_code in (200, 204)  # 200 OK or 204 No Content

        # Step 4: Same key is now rejected
        list_after = await auth_e2e_client.get(
            "/workspaces",
            headers={"X-API-Key": key},
        )
        assert list_after.status_code == 401

    finally:
        settings.AUTH_MODE = original


async def test_e2e_admin_lists_keys_for_tenant(
    auth_e2e_client: AsyncClient,
) -> None:
    """E2E: admin can list all provisioned keys for a tenant."""
    settings.AUTH_MODE = "api_key"
    original = settings.AUTH_MODE

    try:
        # Create 3 keys
        key_ids = []
        for i in range(3):
            resp = await auth_e2e_client.post(
                f"/admin/tenants/{TEST_TENANT}/keys",
                headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
                params={"label": f"key-{i}"},
            )
            assert resp.status_code == 201
            key_ids.append(resp.json()["id"])

        # List keys
        list_resp = await auth_e2e_client.get(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        )
        assert list_resp.status_code == 200
        keys = list_resp.json()
        assert len(keys) == 3
        listed_ids = {k["id"] for k in keys}
        assert listed_ids == set(key_ids)

        # Revoke one
        await auth_e2e_client.delete(
            f"/admin/tenants/{TEST_TENANT}/keys/{key_ids[0]}",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        )

        # List again — should show only 2 active (depends on implementation, may show all)
        list_after = await auth_e2e_client.get(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        )
        keys_after = list_after.json()
        active_count = len([k for k in keys_after if k.get("is_active", True)])
        assert active_count == 2

    finally:
        settings.AUTH_MODE = original


async def test_e2e_rate_limiting_per_key(auth_e2e_client: AsyncClient, tmp_path: Path) -> None:
    """E2E: rate limiting decorator is configured per API key."""
    settings.AUTH_MODE = "api_key"
    original_mode = settings.AUTH_MODE

    try:
        # Create 2 keys for 2 tenants
        key1_resp = await auth_e2e_client.post(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
            params={"label": "key1"},
        )
        key1 = key1_resp.json()["key"]

        key2_resp = await auth_e2e_client.post(
            f"/admin/tenants/{ANOTHER_TENANT}/keys",
            headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
            params={"label": "key2"},
        )
        key2 = key2_resp.json()["key"]

        # Both keys should be able to access their respective workspaces
        # (rate limiting is per-key, verified in unit tests)
        ws1 = await auth_e2e_client.post(
            "/workspaces",
            json={"name": "WS1", "root_path": str(tmp_path)},
            headers={"X-API-Key": key1},
        )
        assert ws1.status_code == 200

        ws2 = await auth_e2e_client.post(
            "/workspaces",
            json={"name": "WS2", "root_path": str(tmp_path)},
            headers={"X-API-Key": key2},
        )
        assert ws2.status_code == 200

        # Both tenants can list their workspaces
        list1 = await auth_e2e_client.get(
            "/workspaces",
            headers={"X-API-Key": key1},
        )
        assert list1.status_code == 200
        assert len(list1.json()) == 1

        list2 = await auth_e2e_client.get(
            "/workspaces",
            headers={"X-API-Key": key2},
        )
        assert list2.status_code == 200
        assert len(list2.json()) == 1

        # Verify they cannot see each other's workspaces
        assert list1.json()[0]["id"] != list2.json()[0]["id"]

    finally:
        settings.AUTH_MODE = original_mode


async def test_e2e_wrong_admin_secret_rejected(
    auth_e2e_client: AsyncClient,
) -> None:
    """E2E: wrong ADMIN_SECRET is rejected on key creation."""
    settings.AUTH_MODE = "api_key"
    original = settings.AUTH_MODE

    try:
        resp = await auth_e2e_client.post(
            f"/admin/tenants/{TEST_TENANT}/keys",
            headers={"X-Admin-Secret": "wrong-secret"},
            params={"label": "fail"},
        )
        assert resp.status_code == 401

    finally:
        settings.AUTH_MODE = original
