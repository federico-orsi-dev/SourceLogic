from __future__ import annotations

from collections.abc import AsyncGenerator

from app.core.config import settings
from app.models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine() -> AsyncEngine:
    connect_args = {"timeout": 30} if "sqlite" in settings.DATABASE_URL else {}
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        connect_args=connect_args,
    )


engine = create_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def configure_sqlite() -> None:
    """Enable WAL journal mode for SQLite to allow concurrent reads during SSE streaming."""
    if "sqlite" not in settings.DATABASE_URL:
        return
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))


async def init_db() -> None:
    # In production, run schema migrations via Alembic:
    #   cd backend && uv run alembic upgrade head
    # create_all is kept here for the test suite (in-memory SQLite, no Alembic).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
