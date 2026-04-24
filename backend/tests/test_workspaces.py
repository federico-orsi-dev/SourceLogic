from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from httpx import AsyncClient


async def test_list_workspaces_empty(client: AsyncClient) -> None:
    response = await client.get("/workspaces")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_workspace_success(client: AsyncClient, tmp_path: Path) -> None:
    response = await client.post(
        "/workspaces", json={"name": "My Repo", "root_path": str(tmp_path)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Repo"
    assert data["root_path"] == str(tmp_path)
    assert data["status"] == "IDLE"
    assert "id" in data


async def test_create_workspace_nonexistent_path(client: AsyncClient) -> None:
    response = await client.post(
        "/workspaces", json={"name": "Bad", "root_path": "/nonexistent/xyz_does_not_exist"}
    )
    assert response.status_code == 404


async def test_create_workspace_path_is_file(client: AsyncClient, tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")
    response = await client.post("/workspaces", json={"name": "Bad", "root_path": str(file_path)})
    assert response.status_code == 400


async def test_create_workspace_duplicate_returns_existing(
    client: AsyncClient, tmp_path: Path
) -> None:
    payload = {"name": "Repo", "root_path": str(tmp_path)}
    first = await client.post("/workspaces", json=payload)
    second = await client.post("/workspaces", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_get_workspace_status(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    status_resp = await client.get(f"/workspaces/{workspace_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "IDLE"


async def test_get_workspace_status_not_found(client: AsyncClient) -> None:
    response = await client.get("/workspaces/99999/status")
    assert response.status_code == 404


async def test_create_session_for_workspace(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    session_resp = await client.post(
        f"/workspaces/{workspace_id}/sessions", json={"title": "My Session"}
    )
    assert session_resp.status_code == 200
    data = session_resp.json()
    assert "session_id" in data
    assert isinstance(data["session_id"], int)


async def test_create_session_default_title(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    session_resp = await client.post(f"/workspaces/{workspace_id}/sessions", json={})
    assert session_resp.status_code == 200
    assert "session_id" in session_resp.json()


async def test_create_session_unknown_workspace(client: AsyncClient) -> None:
    response = await client.post("/workspaces/99999/sessions", json={"title": "Bad"})
    assert response.status_code == 404


async def test_ingest_workspace_returns_queued_task(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    with patch("app.api.v1.workspaces._run_ingestion_task"):
        ingest_resp = await client.post(f"/workspaces/{workspace_id}/ingest")
    assert ingest_resp.status_code == 202
    data = ingest_resp.json()
    assert "task_id" in data
    assert data["status"] == "queued"


async def test_ingest_workspace_not_found(client: AsyncClient) -> None:
    with patch("app.api.v1.workspaces._run_ingestion_task"):
        response = await client.post("/workspaces/99999/ingest")
    assert response.status_code == 404


async def test_get_ingest_status_not_found(client: AsyncClient) -> None:
    response = await client.get("/workspaces/ingest/nonexistent-task-id")
    assert response.status_code == 404


async def test_get_ingest_status_after_queue(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    with patch("app.api.v1.workspaces._run_ingestion_task"):
        ingest_resp = await client.post(f"/workspaces/{workspace_id}/ingest")
    task_id = ingest_resp.json()["task_id"]

    status_resp = await client.get(f"/workspaces/ingest/{task_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "queued"


async def test_delete_workspace(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    with patch("app.api.v1.workspaces.IngestionService") as mock_cls:
        mock_cls.return_value = MagicMock()
        delete_resp = await client.delete(f"/workspaces/{workspace_id}")
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["status"] == "deleted"
    assert data["workspace_id"] == workspace_id


async def test_delete_workspace_not_found(client: AsyncClient) -> None:
    with patch("app.api.v1.workspaces.IngestionService") as mock_cls:
        mock_cls.return_value = MagicMock()
        response = await client.delete("/workspaces/99999")
    assert response.status_code == 404


async def test_delete_removes_workspace_from_list(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    with patch("app.api.v1.workspaces.IngestionService") as mock_cls:
        mock_cls.return_value = MagicMock()
        await client.delete(f"/workspaces/{workspace_id}")
    list_resp = await client.get("/workspaces")
    ids = [w["id"] for w in list_resp.json()]
    assert workspace_id not in ids


async def test_list_sessions_empty(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    response = await client.get(f"/workspaces/{workspace_id}/sessions")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_sessions_returns_created_sessions(client: AsyncClient, tmp_path: Path) -> None:
    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "S1"})
    await client.post(f"/workspaces/{workspace_id}/sessions", json={"title": "S2"})
    list_resp = await client.get(f"/workspaces/{workspace_id}/sessions")
    assert list_resp.status_code == 200
    titles = [s["title"] for s in list_resp.json()]
    assert "S1" in titles
    assert "S2" in titles


async def test_list_sessions_not_found(client: AsyncClient) -> None:
    response = await client.get("/workspaces/99999/sessions")
    assert response.status_code == 404


async def test_create_workspace_path_inside_allowed_base(
    client: AsyncClient, tmp_path: Path
) -> None:
    """When WORKSPACE_ALLOWED_BASE is set, paths inside the base are accepted."""
    from unittest.mock import patch

    from app.core import config as cfg

    with patch.object(cfg.settings, "WORKSPACE_ALLOWED_BASE", str(tmp_path.parent)):
        response = await client.post(
            "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
        )
    assert response.status_code == 200


async def test_create_workspace_path_outside_allowed_base(
    client: AsyncClient, tmp_path: Path
) -> None:
    """When WORKSPACE_ALLOWED_BASE is set, paths outside are rejected with 400."""
    from unittest.mock import patch

    from app.core import config as cfg

    # Use a sibling directory that cannot be under tmp_path.parent / "restricted"
    restricted_base = tmp_path / "restricted"
    restricted_base.mkdir()
    with patch.object(cfg.settings, "WORKSPACE_ALLOWED_BASE", str(restricted_base)):
        response = await client.post(
            "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
        )
    assert response.status_code == 400


async def test_get_ingest_status_wrong_tenant(client: AsyncClient, tmp_path: Path) -> None:
    """Task created by test-tenant must not be visible to another tenant."""
    from app.api.dependencies import get_current_tenant
    from app.main import app

    create_resp = await client.post(
        "/workspaces", json={"name": "Repo", "root_path": str(tmp_path)}
    )
    workspace_id = create_resp.json()["id"]
    with patch("app.api.v1.workspaces._run_ingestion_task"):
        ingest_resp = await client.post(f"/workspaces/{workspace_id}/ingest")
    task_id = ingest_resp.json()["task_id"]

    # Override tenant to a different value for the status check
    app.dependency_overrides[get_current_tenant] = lambda: "other-tenant"
    try:
        status_resp = await client.get(f"/workspaces/ingest/{task_id}")
        assert status_resp.status_code == 404
    finally:
        app.dependency_overrides[get_current_tenant] = lambda: "test-tenant"
