from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.api.dependencies import get_current_tenant
from backend.app.core.database import get_db
from backend.app.models import Session, Workspace
from backend.app.schemas.session import SessionCreate
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceStatusRead
from backend.app.services.db_service import DatabaseService
from backend.app.services.ingest_service import IngestionService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="", tags=["workspaces"])
ingestion_tasks: dict[str, dict[str, Any]] = {}


async def _run_ingestion_task(task_id: str, workspace_id: int) -> None:
    from backend.app.core.database import AsyncSessionLocal

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
) -> list[WorkspaceRead]:
    result = await db.execute(select(Workspace).where(Workspace.tenant_id == tenant_id))
    return list(result.scalars().all())


@router.post("/workspaces", response_model=WorkspaceRead)
async def create_workspace(
    payload: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> WorkspaceRead:
    root_path = Path(payload.root_path)
    if not root_path.exists():
        raise HTTPException(status_code=404, detail="Path not found.")
    if not root_path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory.")

    normalized_root_path = str(root_path.resolve())

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


@router.post("/workspaces/{workspace_id}/sessions")
async def create_session(
    workspace_id: int,
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> dict[str, int]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    title = payload.title or "New Session"
    session = Session(workspace_id=workspace_id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id}


@router.post(
    "/api/v1/workspaces/{workspace_id}/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
@router.post(
    "/workspaces/{workspace_id}/ingest",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_workspace(
    workspace_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> dict[str, str]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    task_id = str(uuid4())
    ingestion_tasks[task_id] = {
        "task_id": task_id,
        "workspace_id": workspace_id,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "error": None,
    }
    background_tasks.add_task(_run_ingestion_task, task_id, workspace_id)
    return {"task_id": task_id, "status": "queued"}


@router.get("/workspaces/ingest/{task_id}")
async def get_ingest_status(task_id: str) -> dict[str, Any]:
    task = ingestion_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Ingestion task not found.")
    return task


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> dict[str, Any]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    try:
        ingestion_service = IngestionService()
        ingestion_service.vectorstore.delete(
            where={
                "$or": [
                    {"workspace_id": workspace_id},
                    {"workspace_id": str(workspace_id)},
                ]
            }
        )
        ingestion_service.vectorstore.persist()
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

    return {"status": "deleted", "workspace_id": workspace_id}
