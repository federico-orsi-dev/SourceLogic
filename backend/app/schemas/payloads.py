from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

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


class ChatRequest(BaseModel):
    query: str
    model: Literal["gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"] = "gpt-4o"
    history: list[Any] | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


class WorkspaceCreate(BaseModel):
    name: str
    root_path: str = Field(..., description="Absolute path to the codebase directory.")

    @field_validator("root_path")
    @classmethod
    def _validate_root_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("root_path must be an absolute path.")
        return value


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    root_path: str
    status: str
    created_at: str
    last_indexed_at: str | None = None


class SessionCreate(BaseModel):
    title: str | None = None


class ChatStreamRequest(BaseModel):
    query: str
    workspace_id: int
    model: Literal["gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"] = "gpt-4o"
    filters: dict[str, list[str]] | None = None
