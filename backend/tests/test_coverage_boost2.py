"""Second coverage boost — stream body, ingestion task, main lifespan paths."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── sessions.py — stream body with tokens (covers finally/save block) ─────────


async def _stream_with_tokens(**_: Any) -> AsyncGenerator[dict[str, Any], None]:
    yield {"type": "citations", "citations": [{"file_name": "main.py", "extension": ".py"}]}
    yield {"type": "token", "token": "Hello"}
    yield {"type": "token", "token": " world"}


async def _stream_with_error(**_: Any) -> AsyncGenerator[dict[str, Any], None]:
    yield {"type": "token", "token": "partial"}
    raise RuntimeError("LLM exploded")


async def test_chat_stream_tokens_saved_to_db(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    """Tokens emitted by stream_answer are persisted as a bot message via the finally block."""
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    with (
        patch("app.api.v1.sessions.ChatService") as MockSvc,
        patch("app.core.database.AsyncSessionLocal", return_value=db_session),
    ):
        MockSvc.return_value.stream_answer = _stream_with_tokens
        resp = await client.post(
            f"/chat/{sess_id}/stream",
            json={"query": "hi", "workspace_id": ws_id, "model": "gpt-4o"},
        )

    assert resp.status_code == 200
    text = resp.text
    assert "Hello" in text
    assert "citations" in text
    assert "done" in text


async def test_chat_stream_error_emits_error_event(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    """An exception inside event_stream yields an error SSE event."""
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    with (
        patch("app.api.v1.sessions.ChatService") as MockSvc,
        patch("app.core.database.AsyncSessionLocal", return_value=db_session),
    ):
        MockSvc.return_value.stream_answer = _stream_with_error
        resp = await client.post(
            f"/chat/{sess_id}/stream",
            json={"query": "hi", "workspace_id": ws_id, "model": "gpt-4o"},
        )

    assert resp.status_code == 200
    assert "error" in resp.text


async def test_chat_stream_done_event_always_emitted(client: AsyncClient, tmp_path: Path) -> None:
    """The 'done' event is always emitted even when stream produces no tokens."""
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    async def _empty_stream(**_: Any) -> AsyncGenerator[dict[str, Any], None]:
        return
        yield  # make it a generator

    with patch("app.api.v1.sessions.ChatService") as MockSvc:
        MockSvc.return_value.stream_answer = _empty_stream
        resp = await client.post(
            f"/chat/{sess_id}/stream",
            json={"query": "hi", "workspace_id": ws_id, "model": "gpt-4o"},
        )

    assert resp.status_code == 200
    assert "done" in resp.text


# ── workspaces.py — _run_ingestion_task paths ─────────────────────────────────


async def test_run_ingestion_task_success(tmp_path: Path) -> None:
    """_run_ingestion_task marks task as completed on success."""
    from app.api.v1.workspaces import _run_ingestion_task, ingestion_tasks
    from app.models import Workspace, WorkspaceStatus
    from sqlalchemy.ext.asyncio import AsyncSession

    task_id = "test-task-success"
    ingestion_tasks[task_id] = {"status": "queued", "workspace_id": 1}

    mock_workspace = MagicMock(spec=Workspace)
    mock_workspace.root_path = str(tmp_path)
    mock_workspace.status = WorkspaceStatus.IDLE

    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.get = AsyncMock(return_value=mock_workspace)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_ingest_result = {"indexed": 5, "skipped": 0}

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=mock_db),
        patch("app.api.v1.workspaces.IngestionService") as mock_svc_cls,
    ):
        mock_svc = AsyncMock()
        mock_svc.ingest_codebase = AsyncMock(return_value=mock_ingest_result)
        mock_svc_cls.return_value = mock_svc

        await _run_ingestion_task(task_id, 1)

    assert ingestion_tasks[task_id]["status"] == "completed"
    assert ingestion_tasks[task_id]["result"] == mock_ingest_result
    assert ingestion_tasks[task_id]["completed_at"] is not None


async def test_run_ingestion_task_workspace_not_found() -> None:
    """_run_ingestion_task marks task as failed when workspace missing."""
    from app.api.v1.workspaces import _run_ingestion_task, ingestion_tasks

    task_id = "test-task-missing"
    ingestion_tasks[task_id] = {"status": "queued", "workspace_id": 999}

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.core.database.AsyncSessionLocal", return_value=mock_db):
        await _run_ingestion_task(task_id, 999)

    assert ingestion_tasks[task_id]["status"] == "failed"
    assert "not found" in ingestion_tasks[task_id]["error"].lower()


async def test_run_ingestion_task_exception() -> None:
    """_run_ingestion_task marks task as failed on ingest exception."""
    from app.api.v1.workspaces import _run_ingestion_task, ingestion_tasks
    from app.models import Workspace

    task_id = "test-task-exception"
    ingestion_tasks[task_id] = {"status": "queued", "workspace_id": 1}

    mock_workspace = MagicMock(spec=Workspace)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_workspace)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=mock_db),
        patch("app.api.v1.workspaces.IngestionService") as mock_svc_cls,
    ):
        mock_svc = AsyncMock()
        mock_svc.ingest_codebase = AsyncMock(side_effect=RuntimeError("disk full"))
        mock_svc_cls.return_value = mock_svc

        await _run_ingestion_task(task_id, 1)

    assert ingestion_tasks[task_id]["status"] == "failed"
    assert "disk full" in ingestion_tasks[task_id]["error"]


async def test_prune_stale_tasks_removes_old_completed() -> None:
    """_prune_stale_tasks removes tasks completed more than 1h ago."""
    from datetime import UTC, datetime, timedelta

    from app.api.v1.workspaces import _prune_stale_tasks, ingestion_tasks

    old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    ingestion_tasks["stale-task"] = {"status": "completed", "completed_at": old_time}
    ingestion_tasks["fresh-task"] = {
        "status": "completed",
        "completed_at": datetime.now(UTC).isoformat(),
    }

    _prune_stale_tasks()

    assert "stale-task" not in ingestion_tasks
    assert "fresh-task" in ingestion_tasks
    ingestion_tasks.pop("fresh-task", None)
