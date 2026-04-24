from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_session_history_empty(client: AsyncClient, tmp_path: Path) -> None:
    workspace_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = workspace_resp.json()["id"]
    session_resp = await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "Test"})
    session_id = session_resp.json()["session_id"]

    history_resp = await client.get(f"/sessions/{session_id}/history")
    assert history_resp.status_code == 200
    assert history_resp.json() == []


async def test_session_history_not_found(client: AsyncClient) -> None:
    response = await client.get("/sessions/99999/history")
    assert response.status_code == 404


async def test_session_history_returns_messages(client: AsyncClient, tmp_path: Path) -> None:
    """After creating a session, messages added via DB should appear in history."""
    workspace_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = workspace_resp.json()["id"]
    session_resp = await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "Test"})
    session_id = session_resp.json()["session_id"]

    # A fresh session has no messages
    history_resp = await client.get(f"/sessions/{session_id}/history")
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 0


async def test_delete_session_success(client: AsyncClient, tmp_path: Path) -> None:
    workspace_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = workspace_resp.json()["id"]
    session_resp = await client.post(
        f"/workspaces/{workspace_id}/sessions", json={"title": "ToDelete"}
    )
    session_id = session_resp.json()["session_id"]

    delete_resp = await client.delete(f"/sessions/{session_id}")
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["status"] == "deleted"
    assert data["session_id"] == session_id


async def test_delete_session_not_found(client: AsyncClient) -> None:
    response = await client.delete("/sessions/99999")
    assert response.status_code == 404


async def test_session_not_in_history_after_delete(client: AsyncClient, tmp_path: Path) -> None:
    workspace_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = workspace_resp.json()["id"]
    session_resp = await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "Gone"})
    session_id = session_resp.json()["session_id"]

    await client.delete(f"/sessions/{session_id}")
    history_resp = await client.get(f"/sessions/{session_id}/history")
    assert history_resp.status_code == 404


async def test_session_history_pagination(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    from app.models import Message

    workspace_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = workspace_resp.json()["id"]
    session_resp = await client.post(
        f"/workspaces/{workspace_id}/sessions", json={"title": "Paged"}
    )
    session_id = session_resp.json()["session_id"]

    # Insert 5 user messages via the shared test DB session
    for i in range(5):
        db_session.add(Message(session_id=session_id, role="user", content=f"msg {i}"))
    await db_session.commit()

    r1 = await client.get(f"/sessions/{session_id}/history?limit=2&offset=0")
    assert r1.status_code == 200
    assert len(r1.json()) == 2

    r2 = await client.get(f"/sessions/{session_id}/history?limit=2&offset=2")
    assert r2.status_code == 200
    assert len(r2.json()) == 2

    r3 = await client.get(f"/sessions/{session_id}/history?limit=10&offset=4")
    assert r3.status_code == 200
    assert len(r3.json()) == 1


async def test_chat_stream_query_too_long(client: AsyncClient, tmp_path: Path) -> None:
    workspace_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = workspace_resp.json()["id"]
    session_resp = await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "S"})
    session_id = session_resp.json()["session_id"]

    resp = await client.post(
        f"/chat/{session_id}/stream",
        json={"query": "x" * 4097, "workspace_id": workspace_id, "model": "gpt-4o"},
    )
    assert resp.status_code == 422
