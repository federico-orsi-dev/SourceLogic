"""Tests targeting specific uncovered lines to push coverage above 85%."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ── logging_config ────────────────────────────────────────────────────────────

async def test_configure_logging_sets_level() -> None:
    from app.core.logging_config import configure_logging

    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG
    configure_logging("INFO")  # restore


async def test_configure_logging_suppresses_noisy_loggers() -> None:
    from app.core.logging_config import configure_logging

    configure_logging("INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("chromadb").level == logging.WARNING
    assert logging.getLogger("sentence_transformers").level == logging.WARNING


async def test_json_formatter_output() -> None:
    from app.core.logging_config import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None,
    )
    output = formatter.format(record)
    import json
    data = json.loads(output)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert "ts" in data


async def test_json_formatter_with_exception() -> None:
    from app.core.logging_config import JsonFormatter

    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error", args=(), exc_info=exc_info,
    )
    output = formatter.format(record)
    import json
    data = json.loads(output)
    assert "exc" in data
    assert "ValueError" in data["exc"]


# ── database ──────────────────────────────────────────────────────────────────

async def test_configure_sqlite_runs_pragma() -> None:
    """configure_sqlite() should execute WAL pragma without error."""
    from app.core.database import configure_sqlite

    # Should not raise — uses the real engine (in-memory for tests won't apply,
    # but the function itself must be callable)
    await configure_sqlite()


async def test_get_db_yields_session() -> None:
    from app.core.database import get_db

    gen = get_db()
    session = await gen.__anext__()
    assert session is not None
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


# ── limiter ───────────────────────────────────────────────────────────────────

async def test_rate_limit_key_api_key() -> None:
    from app.core.limiter import _rate_limit_key
    from starlette.requests import Request
    from starlette.datastructures import Headers

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(b"x-api-key", b"mysecretkey")],
    }
    request = Request(scope)
    key = _rate_limit_key(request)
    assert key.startswith("apikey:")


async def test_rate_limit_key_tenant_id() -> None:
    from app.core.limiter import _rate_limit_key
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(b"x-tenant-id", b"my-tenant")],
    }
    request = Request(scope)
    key = _rate_limit_key(request)
    assert key == "tenant:my-tenant"


async def test_rate_limit_key_falls_back_to_ip() -> None:
    from app.core.limiter import _rate_limit_key
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
    }
    request = Request(scope)
    key = _rate_limit_key(request)
    assert "127.0.0.1" in key


# ── sessions — error paths ─────────────────────────────────────────────────────

async def test_session_history_wrong_tenant(client: AsyncClient, tmp_path: Path) -> None:
    """Session belonging to another tenant returns 404."""
    from app.api.dependencies import get_current_tenant
    from app.main import app

    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    app.dependency_overrides[get_current_tenant] = lambda: "other-tenant"
    try:
        r = await client.get(f"/sessions/{sess_id}/history")
        assert r.status_code == 404
    finally:
        app.dependency_overrides[get_current_tenant] = lambda: "test-tenant"


async def test_delete_session_wrong_tenant(client: AsyncClient, tmp_path: Path) -> None:
    from app.api.dependencies import get_current_tenant
    from app.main import app

    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    app.dependency_overrides[get_current_tenant] = lambda: "other-tenant"
    try:
        r = await client.delete(f"/sessions/{sess_id}")
        assert r.status_code == 404
    finally:
        app.dependency_overrides[get_current_tenant] = lambda: "test-tenant"


async def test_stream_chat_session_not_found(client: AsyncClient, tmp_path: Path) -> None:
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    r = await client.post(
        "/chat/99999/stream",
        json={"query": "hi", "workspace_id": ws_id, "model": "gpt-4o"},
    )
    assert r.status_code == 404


async def test_stream_chat_workspace_not_found(client: AsyncClient, tmp_path: Path) -> None:
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    r = await client.post(
        f"/chat/{sess_id}/stream",
        json={"query": "hi", "workspace_id": 99999, "model": "gpt-4o"},
    )
    assert r.status_code == 404


async def test_stream_chat_wrong_tenant_workspace(client: AsyncClient, tmp_path: Path) -> None:
    from app.api.dependencies import get_current_tenant
    from app.main import app

    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]
    sess = await client.post(f"/workspaces/{ws_id}/sessions", json={"title": "S"})
    sess_id = sess.json()["session_id"]

    app.dependency_overrides[get_current_tenant] = lambda: "other-tenant"
    try:
        r = await client.post(
            f"/chat/{sess_id}/stream",
            json={"query": "hi", "workspace_id": ws_id, "model": "gpt-4o"},
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides[get_current_tenant] = lambda: "test-tenant"


# ── workspaces — ingest duplicate + delete error paths ────────────────────────

async def test_ingest_duplicate_task_returns_409(client: AsyncClient, tmp_path: Path) -> None:
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]

    with patch("app.api.v1.workspaces._run_ingestion_task"):
        r1 = await client.post(f"/workspaces/{ws_id}/ingest")
        assert r1.status_code == 202

        # Manually mark the task as still running
        from app.api.v1.workspaces import ingestion_tasks
        task_id = r1.json()["task_id"]
        ingestion_tasks[task_id]["status"] = "running"

        r2 = await client.post(f"/workspaces/{ws_id}/ingest")
        assert r2.status_code == 409


async def test_delete_workspace_vector_error_returns_500(
    client: AsyncClient, tmp_path: Path
) -> None:
    ws = await client.post("/workspaces", json={"name": "R", "root_path": str(tmp_path)})
    ws_id = ws.json()["id"]

    with patch("app.api.v1.workspaces.IngestionService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.vectorstore.delete.side_effect = RuntimeError("vector store down")
        mock_cls.return_value = mock_instance
        r = await client.delete(f"/workspaces/{ws_id}")
    assert r.status_code == 500


# ── admin — revoke already inactive / not-owner ───────────────────────────────

async def test_revoke_api_key_wrong_tenant(client: AsyncClient) -> None:
    """Revoking a key belonging to a different tenant returns 404."""
    import os
    from app.core.config import settings

    with patch.object(settings, "ADMIN_SECRET", "test-admin-secret"):
        create_r = await client.post(
            "/admin/tenants/tenant-x/keys",
            headers={"X-Admin-Secret": "test-admin-secret"},
            params={"label": "test"},
        )
        assert create_r.status_code == 201
        key_id = create_r.json()["id"]

        # Try to revoke it under a different tenant_id
        delete_r = await client.delete(
            f"/admin/tenants/tenant-y/keys/{key_id}",
            headers={"X-Admin-Secret": "test-admin-secret"},
        )
        assert delete_r.status_code == 404


async def test_admin_no_secret_configured_returns_503(client: AsyncClient) -> None:
    from app.core.config import settings

    with patch.object(settings, "ADMIN_SECRET", None):
        r = await client.post(
            "/admin/tenants/t/keys",
            headers={"X-Admin-Secret": "anything"},
        )
    assert r.status_code == 503


async def test_admin_wrong_secret_returns_401(client: AsyncClient) -> None:
    from app.core.config import settings

    with patch.object(settings, "ADMIN_SECRET", "correct-secret"):
        r = await client.post(
            "/admin/tenants/t/keys",
            headers={"X-Admin-Secret": "wrong-secret"},
        )
    assert r.status_code == 401
