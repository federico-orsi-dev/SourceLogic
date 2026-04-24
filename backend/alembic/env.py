from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from typing import Any

# alembic.ini lives in backend/ but the app package is rooted one level up.
# Add the project root (parent of backend/) so `app.*` is importable.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Import application settings and ORM metadata
from app.core.config import settings
from app.models.models import Base

# ── Alembic Config object ────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate support: point at the full ORM metadata
target_metadata = Base.metadata


# ── Offline migrations (SQL script output) ───────────────────────────────────
def run_migrations_offline() -> None:
    """Emit SQL to stdout; no DB connection required."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite ALTER TABLE compatibility
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (async DB connection) ───────────────────────────────────
def do_run_migrations(connection: Any) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite ALTER TABLE compatibility
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Apply migrations via an async engine."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
