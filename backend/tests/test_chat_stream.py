from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import patch

from httpx import AsyncClient


async def _fake_stream(**_: Any) -> AsyncGenerator[dict[str, Any], None]:
    """Minimal async generator — no tokens, so the finally block skips DB write."""
    yield {"type": "citations", "citations": []}


async def test_chat_stream_success(client: AsyncClient, tmp_path: Path) -> None:
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    workspace_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "S"})
    session_id = sess.json()["session_id"]

    with patch("app.api.v1.sessions.ChatService") as MockSvc:
        MockSvc.return_value.stream_answer = _fake_stream
        resp = await client.post(
            f"/chat/{session_id}/stream",
            json={"query": "what is this?", "workspace_id": workspace_id, "model": "gpt-4o"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "citations" in resp.text


async def test_chat_stream_session_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/chat/99999/stream",
        json={"query": "x", "workspace_id": 1, "model": "gpt-4o"},
    )
    assert resp.status_code == 404


async def test_chat_stream_workspace_mismatch(client: AsyncClient, tmp_path: Path) -> None:
    """Session belongs to workspace A but request passes workspace B — expect 404."""
    path_a = tmp_path / "a"
    path_a.mkdir()
    ws_a = await client.post("/workspaces", json={"name": "A", "root_path": str(path_a)})
    workspace_a_id = ws_a.json()["id"]

    path_b = tmp_path / "b"
    path_b.mkdir()
    ws_b = await client.post("/workspaces", json={"name": "B", "root_path": str(path_b)})
    workspace_b_id = ws_b.json()["id"]

    sess = await client.post(f"/workspaces/{workspace_a_id}/sessions", json={"title": "S"})
    session_id = sess.json()["session_id"]

    resp = await client.post(
        f"/chat/{session_id}/stream",
        json={"query": "x", "workspace_id": workspace_b_id, "model": "gpt-4o"},
    )
    assert resp.status_code == 404
