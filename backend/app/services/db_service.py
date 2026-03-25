from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime

from backend.app.core.database import get_db
from backend.app.models import Message, Session, Workspace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Deprecated alias kept for backward compatibility.

    Source of truth for engine/session lifecycle is backend.app.core.database.
    """
    async for session in get_db():
        yield session


class DatabaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_workspace(self, name: str, root_path: str) -> Workspace:
        workspace = Workspace(name=name, root_path=root_path)
        self.session.add(workspace)
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def list_workspaces(self) -> list[Workspace]:
        result = await self.session.execute(select(Workspace))
        return list(result.scalars().all())

    async def get_workspace(self, workspace_id: int) -> Workspace | None:
        result = await self.session.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def update_workspace_status(self, workspace_id: int, status: str) -> None:
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            return
        workspace.status = status
        await self.session.commit()

    async def update_last_indexed_at(self, workspace_id: int, timestamp: datetime) -> None:
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            return
        workspace.last_indexed_at = timestamp
        await self.session.commit()

    async def create_chat_session(self, workspace_id: int, title: str) -> Session:
        session = Session(workspace_id=workspace_id, title=title)
        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)
        return session

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        sources: dict | None = None,
        timestamp: datetime | None = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def list_messages(self, session_id: int) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp.asc())
        )
        return list(result.scalars().all())
