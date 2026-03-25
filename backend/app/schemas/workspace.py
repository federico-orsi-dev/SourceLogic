from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from backend.app.models import WorkspaceStatus


class WorkspaceCreate(BaseModel):
    name: str
    root_path: str = Field(..., description="Absolute path to the codebase directory.")


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    root_path: str
    status: WorkspaceStatus
    last_indexed_at: datetime | None = None
    created_at: datetime


class WorkspaceStatusRead(BaseModel):
    status: WorkspaceStatus
