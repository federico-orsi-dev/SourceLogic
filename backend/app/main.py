from __future__ import annotations

import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from app.api.v1 import admin_router, sessions_router, workspaces_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, configure_sqlite, get_db
from app.core.limiter import limiter
from app.core.logging_config import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.models import Workspace, WorkspaceStatus
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(settings.LOG_LEVEL)
    await configure_sqlite()
    if not settings.OPENAI_API_KEY:
        warnings.warn(
            "OPENAI_API_KEY is not set — /chat endpoints will fail at runtime",
            stacklevel=1,
        )
    # Reset any workspaces left in INDEXING state by a previously crashed process.
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Workspace)
            .where(Workspace.status == WorkspaceStatus.INDEXING)
            .values(status=WorkspaceStatus.FAILED)
        )
        await session.commit()
    yield


app = FastAPI(title="SourceLogic API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces_router)
app.include_router(sessions_router)
app.include_router(admin_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result: dict[str, object] = {"status": "ok"}
    try:
        await db.execute(text("SELECT 1"))
        result["db"] = True
    except Exception:  # noqa: BLE001
        result["db"] = False
        result["status"] = "degraded"
    result["llm_configured"] = bool(settings.OPENAI_API_KEY)
    return result
