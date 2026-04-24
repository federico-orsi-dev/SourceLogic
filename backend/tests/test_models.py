from __future__ import annotations

from app.models import Message, Session, Workspace, WorkspaceStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_workspace_cascade_deletes_sessions(db_session: AsyncSession) -> None:
    workspace = Workspace(name="Test", root_path="/tmp/repo_cascade", tenant_id="t1")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    chat_session = Session(workspace_id=workspace.id, title="Chat")
    db_session.add(chat_session)
    await db_session.commit()

    await db_session.delete(workspace)
    await db_session.commit()

    result = await db_session.execute(select(Session).where(Session.workspace_id == workspace.id))
    assert result.scalars().all() == []


async def test_session_cascade_deletes_messages(db_session: AsyncSession) -> None:
    workspace = Workspace(name="Test", root_path="/tmp/repo_msg", tenant_id="t1")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    chat_session = Session(workspace_id=workspace.id, title="Chat")
    db_session.add(chat_session)
    await db_session.commit()
    await db_session.refresh(chat_session)

    message = Message(session_id=chat_session.id, role="user", content="Hello")
    db_session.add(message)
    await db_session.commit()

    await db_session.delete(chat_session)
    await db_session.commit()

    result = await db_session.execute(select(Message).where(Message.session_id == chat_session.id))
    assert result.scalars().all() == []


async def test_workspace_default_status_is_idle(db_session: AsyncSession) -> None:
    workspace = Workspace(name="Test", root_path="/tmp/repo_idle", tenant_id="t1")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    assert workspace.status == WorkspaceStatus.IDLE


def test_workspace_status_enum_values() -> None:
    assert WorkspaceStatus.IDLE == "IDLE"
    assert WorkspaceStatus.INDEXING == "INDEXING"
    assert WorkspaceStatus.FAILED == "FAILED"


async def test_workspace_last_indexed_at_null_by_default(db_session: AsyncSession) -> None:
    workspace = Workspace(name="Test", root_path="/tmp/repo_null", tenant_id="t1")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    assert workspace.last_indexed_at is None
