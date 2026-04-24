from __future__ import annotations

from datetime import UTC, datetime

from app.models import WorkspaceStatus
from app.services.db_service import DatabaseService
from sqlalchemy.ext.asyncio import AsyncSession

TEST_TENANT = "tenant-a"


async def test_create_workspace(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    workspace = await service.create_workspace("Test Repo", "/tmp/repo", TEST_TENANT)
    assert workspace.id is not None
    assert workspace.name == "Test Repo"
    assert workspace.root_path == "/tmp/repo"
    assert workspace.status == WorkspaceStatus.IDLE


async def test_list_workspaces(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    await service.create_workspace("Repo A", "/tmp/a", TEST_TENANT)
    await service.create_workspace("Repo B", "/tmp/b", TEST_TENANT)
    workspaces = await service.list_workspaces(TEST_TENANT)
    assert len(workspaces) == 2


async def test_list_workspaces_tenant_isolation(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    await service.create_workspace("Repo A", "/tmp/a", "tenant-x")
    await service.create_workspace("Repo B", "/tmp/b", "tenant-y")
    assert len(await service.list_workspaces("tenant-x")) == 1
    assert len(await service.list_workspaces("tenant-y")) == 1
    assert len(await service.list_workspaces("tenant-z")) == 0


async def test_get_workspace(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    created = await service.create_workspace("Repo", "/tmp/repo", TEST_TENANT)
    fetched = await service.get_workspace(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Repo"


async def test_get_workspace_not_found(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    result = await service.get_workspace(99999)
    assert result is None


async def test_update_workspace_status(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    workspace = await service.create_workspace("Repo", "/tmp/repo", TEST_TENANT)
    assert workspace.status == WorkspaceStatus.IDLE

    await service.update_workspace_status(workspace.id, WorkspaceStatus.INDEXING)
    updated = await service.get_workspace(workspace.id)
    assert updated is not None
    assert updated.status == WorkspaceStatus.INDEXING


async def test_update_workspace_status_not_found_is_noop(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    await service.update_workspace_status(99999, WorkspaceStatus.FAILED)


async def test_update_last_indexed_at(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    workspace = await service.create_workspace("Repo", "/tmp/repo", TEST_TENANT)
    assert workspace.last_indexed_at is None

    now = datetime.now(UTC)
    await service.update_last_indexed_at(workspace.id, now)
    updated = await service.get_workspace(workspace.id)
    assert updated is not None
    assert updated.last_indexed_at is not None


async def test_create_chat_session(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    workspace = await service.create_workspace("Repo", "/tmp/repo", TEST_TENANT)
    session = await service.create_chat_session(workspace.id, "My Chat")
    assert session.id is not None
    assert session.workspace_id == workspace.id
    assert session.title == "My Chat"


async def test_add_message_and_list_messages(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    workspace = await service.create_workspace("Repo", "/tmp/repo", TEST_TENANT)
    chat_session = await service.create_chat_session(workspace.id, "Chat")

    await service.add_message(chat_session.id, "user", "Hello?")
    await service.add_message(chat_session.id, "bot", "Hi there!")

    messages = await service.list_messages(chat_session.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hello?"
    assert messages[1].role == "bot"
    assert messages[1].content == "Hi there!"


async def test_list_messages_empty(db_session: AsyncSession) -> None:
    service = DatabaseService(db_session)
    workspace = await service.create_workspace("Repo", "/tmp/repo", TEST_TENANT)
    chat_session = await service.create_chat_session(workspace.id, "Empty Chat")
    messages = await service.list_messages(chat_session.id)
    assert messages == []
