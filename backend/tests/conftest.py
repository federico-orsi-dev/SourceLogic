from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from app.api.dependencies import get_current_tenant
from app.api.v1.workspaces import ingestion_tasks
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

TEST_TENANT = "test-tenant"
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def clear_ingestion_tasks() -> None:
    ingestion_tasks.clear()


@pytest_asyncio.fixture
async def _test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Shared in-memory engine for a single test — all fixtures in the same test use this."""
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(_test_engine) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[no-untyped-def]
    """AsyncClient wired to an isolated in-memory SQLite database per test."""
    session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def _override_get_tenant() -> str:
        return TEST_TENANT

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_tenant] = _override_get_tenant

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(_test_engine) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[no-untyped-def]
    """Direct AsyncSession sharing the same in-memory DB as `client` within a test."""
    session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
