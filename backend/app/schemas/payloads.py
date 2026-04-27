from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class IngestRequest(BaseModel):
    path: str = Field(..., description="Absolute path to the codebase directory.")
    exclude_patterns: list[str] = Field(default_factory=list)
    include_extensions: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _validate_absolute_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("path must be an absolute path.")
        return value

    @field_validator("include_extensions")
    @classmethod
    def _validate_include_extensions(cls, value: list[str]) -> list[str]:
        cleaned = []
        for ext in value:
            normalized = ext.strip().lower()
            if not normalized:
                continue
            if not normalized.startswith("."):
                normalized = f".{normalized}"
            cleaned.append(normalized)
        return cleaned


class ChatStreamFilters(BaseModel):
    include_extensions: list[str] | None = None
    exclude_folders: list[str] | None = None


class ChatStreamPayload(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    workspace_id: int
    model: Literal["gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"] = "gpt-4o"
    filters: ChatStreamFilters | None = None

    @field_validator("query")
    @classmethod
    def _strip_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace only")
        return stripped


class SessionCreateResponse(BaseModel):
    session_id: int


class IngestTaskResponse(BaseModel):
    task_id: str
    status: str


class IngestStatusResponse(BaseModel):
    task_id: str
    workspace_id: int
    status: str
    created_at: str
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, int] | None = None


class DeleteResponse(BaseModel):
    status: str
    workspace_id: int


class SessionDeleteResponse(BaseModel):
    status: str
    session_id: int
