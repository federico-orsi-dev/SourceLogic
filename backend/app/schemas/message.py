from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageRole(StrEnum):
    USER = "user"
    BOT = "bot"


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: MessageRole
    content: str
    sources: dict[str, Any] | None = None
    is_complete: bool = True
    timestamp: datetime
