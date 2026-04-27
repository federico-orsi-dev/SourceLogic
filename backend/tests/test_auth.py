from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from app.api.v1.workspaces import ingestion_tasks
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import Base, TenantAPIKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
REAL_KEY = "test-secret-key-for-auth-tests"
REAL_KEY_HASH = hashlib.sha256(REAL_KEY.encode()).hexdigest()


@pytest_asyncio.fixture
async def auth_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def auth_client(auth_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Client with NO dependency overrides — tests real auth logic."""
    ingestion_tasks.clear()
    session_factory = async_sessionmaker(auth_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    # Intentionally NOT overriding get_current_tenant — we test real auth.

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def active_key(auth_engine: AsyncEngine) -> str:
    """Insert an active API key into the DB and return the plaintext key."""
    session_factory = async_sessionmaker(auth_engine, expire_on_commit=False)
    async with session_factory() as session:
        record = TenantAPIKey(
            tenant_id="tenant-alpha",
            key_hash=REAL_KEY_HASH,
            label="test",
            is_active=True,
        )
        session.add(record)
        await session.commit()
    return REAL_KEY


@pytest_asyncio.fixture
async def revoked_key(auth_engine: AsyncEngine) -> str:
    """Insert a revoked API key into the DB and return the plaintext key."""
    revoked = "revoked-key-for-testing"
    revoked_hash = hashlib.sha256(revoked.encode()).hexdigest()
    session_factory = async_sessionmaker(auth_engine, expire_on_commit=False)
    async with session_factory() as session:
        record = TenantAPIKey(
            tenant_id="tenant-alpha",
            key_hash=revoked_hash,
            label="revoked",
            is_active=False,
        )
        session.add(record)
        await session.commit()
    return revoked


# ── dev mode (AUTH_MODE=dev) ───────────────────────────────────────────────


async def test_dev_mode_no_header_uses_default_tenant(auth_client: AsyncClient) -> None:
    """In dev mode, missing X-Tenant-ID falls back to 'tenant-a' — no 401."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "dev"
    try:
        resp = await auth_client.get("/workspaces")
        assert resp.status_code == 200
    finally:
        settings.AUTH_MODE = original


async def test_dev_mode_custom_tenant_header(auth_client: AsyncClient) -> None:
    """In dev mode, X-Tenant-ID header is trusted directly."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "dev"
    try:
        resp = await auth_client.get("/workspaces", headers={"X-Tenant-ID": "my-org"})
        assert resp.status_code == 200
    finally:
        settings.AUTH_MODE = original


# ── api_key mode (AUTH_MODE=api_key) ──────────────────────────────────────


async def test_api_key_mode_no_key_returns_401(auth_client: AsyncClient) -> None:
    """In api_key mode, a request without X-API-Key must be rejected."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "api_key"
    try:
        resp = await auth_client.get("/workspaces")
        assert resp.status_code == 401
        assert "X-API-Key" in resp.json()["detail"]
    finally:
        settings.AUTH_MODE = original


async def test_api_key_mode_invalid_key_returns_401(auth_client: AsyncClient) -> None:
    """A key not present in the DB must return 401."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "api_key"
    try:
        resp = await auth_client.get("/workspaces", headers={"X-API-Key": "not-a-real-key"})
        assert resp.status_code == 401
    finally:
        settings.AUTH_MODE = original


async def test_api_key_mode_revoked_key_returns_401(
    auth_client: AsyncClient, revoked_key: str
) -> None:
    """A key with is_active=False must return 401."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "api_key"
    try:
        resp = await auth_client.get("/workspaces", headers={"X-API-Key": revoked_key})
        assert resp.status_code == 401
    finally:
        settings.AUTH_MODE = original


async def test_api_key_mode_valid_key_returns_200(
    auth_client: AsyncClient, active_key: str
) -> None:
    """A valid, active API key must be accepted and return 200."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "api_key"
    try:
        resp = await auth_client.get("/workspaces", headers={"X-API-Key": active_key})
        assert resp.status_code == 200
    finally:
        settings.AUTH_MODE = original


async def test_api_key_mode_extracts_correct_tenant(
    auth_client: AsyncClient, active_key: str, tmp_path: Path
) -> None:
    """The tenant resolved from the API key is used for workspace isolation."""
    original = settings.AUTH_MODE
    settings.AUTH_MODE = "api_key"
    try:
        # Create a workspace under tenant-alpha
        resp = await auth_client.post(
            "/workspaces",
            json={"name": "Alpha Repo", "root_path": str(tmp_path)},
            headers={"X-API-Key": active_key},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "tenant-alpha"

        # A different key (or no key) cannot see it
        resp2 = await auth_client.get("/workspaces", headers={"X-API-Key": "wrong"})
        assert resp2.status_code == 401
    finally:
        settings.AUTH_MODE = original


# ── admin endpoint protection ─────────────────────────────────────────────


async def test_admin_no_secret_configured_returns_503(auth_client: AsyncClient) -> None:
    """When ADMIN_SECRET is not configured, admin endpoints return 503."""
    original = settings.ADMIN_SECRET
    settings.ADMIN_SECRET = None
    try:
        resp = await auth_client.post(
            "/admin/tenants/t1/keys", headers={"X-Admin-Secret": "anything"}
        )
        assert resp.status_code == 503
    finally:
        settings.ADMIN_SECRET = original


async def test_admin_wrong_secret_returns_401(auth_client: AsyncClient) -> None:
    original = settings.ADMIN_SECRET
    settings.ADMIN_SECRET = "correct-secret"
    try:
        resp = await auth_client.post(
            "/admin/tenants/t1/keys", headers={"X-Admin-Secret": "wrong-secret"}
        )
        assert resp.status_code == 401
    finally:
        settings.ADMIN_SECRET = original


async def test_admin_correct_secret_creates_key(auth_client: AsyncClient) -> None:
    original = settings.ADMIN_SECRET
    settings.ADMIN_SECRET = "correct-secret"
    try:
        resp = await auth_client.post(
            "/admin/tenants/t1/keys",
            headers={"X-Admin-Secret": "correct-secret"},
            params={"label": "ci"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tenant_id"] == "t1"
        assert data["label"] == "ci"
        assert len(data["key"]) > 20  # plaintext key returned once
    finally:
        settings.ADMIN_SECRET = original


# ── input validation ───────────────────────────────────────────────────────


async def test_workspace_name_empty_returns_422(auth_client: AsyncClient, tmp_path: Path) -> None:
    resp = await auth_client.post(
        "/workspaces",
        json={"name": "", "root_path": str(tmp_path)},
        headers={"X-Tenant-ID": "t1"},
    )
    assert resp.status_code == 422


async def test_workspace_name_too_long_returns_422(
    auth_client: AsyncClient, tmp_path: Path
) -> None:
    resp = await auth_client.post(
        "/workspaces",
        json={"name": "x" * 201, "root_path": str(tmp_path)},
        headers={"X-Tenant-ID": "t1"},
    )
    assert resp.status_code == 422


async def test_chat_query_whitespace_only_returns_422(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/chat/999/stream",
        json={"query": "   ", "workspace_id": 1, "model": "gpt-4o"},
        headers={"X-Tenant-ID": "t1"},
    )
    assert resp.status_code == 422
