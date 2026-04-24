from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.api.dependencies import get_current_tenant
from app.core.config import settings
from app.core.database import get_db
from app.models import Session, Workspace
from app.schemas.payloads import (
    DeleteResponse,
    IngestStatusResponse,
    IngestTaskResponse,
    SessionCreateResponse,
)
from app.schemas.session import SessionCreate, SessionRead
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceStatusRead
from app.services.db_service import DatabaseService
from app.services.ingest_service import IngestionService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="", tags=["workspaces"])
ingestion_tasks: dict[str, dict[str, Any]] = {}

_TASK_TTL = timedelta(hours=1)


def _prune_stale_tasks() -> None:
    """Remove completed ingestion tasks older than _TASK_TTL to prevent unbounded growth."""
    cutoff = datetime.now(UTC) - _TASK_TTL
    stale = [
        tid
        for tid, task in ingestion_tasks.items()
        if task.get("completed_at") is not None
        and datetime.fromisoformat(task["completed_at"]) < cutoff
    ]
    for tid in stale:
        ingestion_tasks.pop(tid, None)


async def _run_ingestion_task(task_id: str, workspace_id: int) -> None:
    from app.core.database import AsyncSessionLocal

    ingestion_tasks[task_id]["status"] = "running"

    async with AsyncSessionLocal() as db_session:
        db_service = DatabaseService(db_session)
        workspace = await db_session.get(Workspace, workspace_id)
        if workspace is None:
            ingestion_tasks[task_id]["status"] = "failed"
            ingestion_tasks[task_id]["error"] = "Workspace not found."
            ingestion_tasks[task_id]["completed_at"] = datetime.now(UTC).isoformat()
            return

        service = IngestionService()
        try:
            result = await service.ingest_codebase(workspace, db_service)
            ingestion_tasks[task_id]["status"] = "completed"
            ingestion_tasks[task_id]["result"] = result
        except Exception as exc:  # noqa: BLE001
            ingestion_tasks[task_id]["status"] = "failed"
            ingestion_tasks[task_id]["error"] = str(exc)
        finally:
            ingestion_tasks[task_id]["completed_at"] = datetime.now(UTC).isoformat()


@router.get("/workspaces", response_model=list[WorkspaceRead])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> list[Workspace]:
    result = await db.execute(select(Workspace).where(Workspace.tenant_id == tenant_id))
    return list(result.scalars().all())


@router.post("/workspaces", response_model=WorkspaceRead)
async def create_workspace(
    payload: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> Workspace:
    root_path = Path(payload.root_path)
    if not root_path.exists():
        raise HTTPException(status_code=404, detail="Path not found.")
    if not root_path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory.")

    normalized_root_path = str(root_path.resolve())

    if settings.WORKSPACE_ALLOWED_BASE:
        allowed = Path(settings.WORKSPACE_ALLOWED_BASE).resolve()
        if not root_path.resolve().is_relative_to(allowed):
            raise HTTPException(
                status_code=400,
                detail="Path must be within the configured workspace base directory.",
            )

    existing_result = await db.execute(
        select(Workspace).where(
            func.lower(Workspace.root_path) == normalized_root_path.lower(),
            Workspace.tenant_id == tenant_id,
        )
    )
    existing_workspace = existing_result.scalar_one_or_none()
    if existing_workspace is not None:
        return existing_workspace

    workspace = Workspace(
        name=payload.name,
        root_path=normalized_root_path,
        tenant_id=tenant_id,
    )
    db.add(workspace)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        existing_result = await db.execute(
            select(Workspace).where(
                func.lower(Workspace.root_path) == normalized_root_path.lower(),
                Workspace.tenant_id == tenant_id,
            )
        )
        existing_workspace = existing_result.scalar_one_or_none()
        if existing_workspace is not None:
            return existing_workspace
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace path already exists.",
        ) from exc

    await db.refresh(workspace)
    return workspace


@router.get("/workspaces/{workspace_id}/status", response_model=WorkspaceStatusRead)
async def get_workspace_status(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> WorkspaceStatusRead:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return WorkspaceStatusRead(status=workspace.status)


@router.get("/workspaces/{workspace_id}/sessions", response_model=list[SessionRead])
async def list_sessions(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> list[Session]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    result = await db.execute(
        select(Session)
        .where(Session.workspace_id == workspace_id)
        .order_by(Session.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/workspaces/{workspace_id}/sessions", response_model=SessionCreateResponse)
async def create_session(
    workspace_id: int,
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> SessionCreateResponse:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    title = payload.title or "New Session"
    session = Session(workspace_id=workspace_id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionCreateResponse(session_id=session.id)


@router.post(
    "/workspaces/{workspace_id}/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestTaskResponse,
)
async def ingest_workspace(
    workspace_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> IngestTaskResponse:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    _prune_stale_tasks()

    active = [
        t
        for t in ingestion_tasks.values()
        if t.get("workspace_id") == workspace_id and t.get("status") in ("queued", "running")
    ]
    if active:
        raise HTTPException(
            status_code=409,
            detail="An ingestion task is already running for this workspace.",
        )

    task_id = str(uuid4())
    ingestion_tasks[task_id] = {
        "task_id": task_id,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "error": None,
    }
    background_tasks.add_task(_run_ingestion_task, task_id, workspace_id)
    return IngestTaskResponse(task_id=task_id, status="queued")


@router.get("/workspaces/ingest/{task_id}", response_model=IngestStatusResponse)
async def get_ingest_status(
    task_id: str,
    tenant_id: str = Depends(get_current_tenant),
) -> IngestStatusResponse:
    _prune_stale_tasks()
    task = ingestion_tasks.get(task_id)
    if not task or task.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Ingestion task not found.")
    return IngestStatusResponse(**task)


@router.delete("/workspaces/{workspace_id}", response_model=DeleteResponse)
async def delete_workspace(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> DeleteResponse:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    def _delete_vectors_sync(wid: int) -> None:
        svc = IngestionService()
        svc.vectorstore.delete(where={"$or": [{"workspace_id": wid}, {"workspace_id": str(wid)}]})

    try:
        await asyncio.to_thread(_delete_vectors_sync, workspace_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clean workspace vectors: {exc}",
        ) from exc

    try:
        await db.delete(workspace)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete workspace: {exc}",
        ) from exc

    for task_id, task in list(ingestion_tasks.items()):
        if task.get("workspace_id") == workspace_id:
            ingestion_tasks.pop(task_id, None)

    return DeleteResponse(status="deleted", workspace_id=workspace_id)
