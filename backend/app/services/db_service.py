from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models import Message, Session, Workspace, WorkspaceStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_workspace(self, name: str, root_path: str, tenant_id: str) -> Workspace:
        workspace = Workspace(name=name, root_path=root_path, tenant_id=tenant_id)
        self.session.add(workspace)
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def list_workspaces(self, tenant_id: str) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace).where(Workspace.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def get_workspace(self, workspace_id: int) -> Workspace | None:
        result = await self.session.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def update_workspace_status(self, workspace_id: int, status: WorkspaceStatus) -> None:
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
        sources: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            timestamp=timestamp or datetime.now(UTC),
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
