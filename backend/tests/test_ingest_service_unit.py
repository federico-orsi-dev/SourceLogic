"""Unit tests for IngestionService with mocked CodeParser and Chroma."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import Workspace, WorkspaceStatus
from app.services.db_service import DatabaseService


def _make_workspace(tmp_path: object) -> Workspace:
    ws = Workspace()
    ws.id = 1
    ws.name = "Test"
    ws.root_path = str(tmp_path)
    ws.tenant_id = "t"
    ws.status = WorkspaceStatus.IDLE
    return ws


async def test_ingest_skips_unchanged_files(tmp_path: object) -> None:
    ws = _make_workspace(tmp_path)
    mock_db = AsyncMock(spec=DatabaseService)

    with (
        patch("app.services.ingest_service.CodeParser") as MockParser,
        patch("app.services.ingest_service.Chroma"),
    ):
        MockParser.return_value.scan.return_value = ([], [])
        MockParser.return_value.persist_manifest.return_value = None

        from app.services.ingest_service import IngestionService

        svc = IngestionService(persist_directory=str(tmp_path))
        result = await svc.ingest_codebase(ws, mock_db)

    assert result["chunks_created"] == 0
    assert result["files_processed"] == 0
    assert result["files_removed"] == 0


async def test_ingest_invalid_path_sets_failed(tmp_path: object) -> None:
    ws = _make_workspace(tmp_path)
    ws.root_path = "/nonexistent/path/that/does/not/exist"
    mock_db = AsyncMock(spec=DatabaseService)

    with (
        patch("app.services.ingest_service.CodeParser"),
        patch("app.services.ingest_service.Chroma"),
    ):
        from app.services.ingest_service import IngestionService

        svc = IngestionService(persist_directory=str(tmp_path))
        with pytest.raises(ValueError, match="Invalid source_path"):
            await svc.ingest_codebase(ws, mock_db)

    mock_db.update_workspace_status.assert_called_with(ws.id, WorkspaceStatus.FAILED)


async def test_ingest_sets_idle_on_success(tmp_path: object) -> None:
    ws = _make_workspace(tmp_path)
    mock_db = AsyncMock(spec=DatabaseService)

    with (
        patch("app.services.ingest_service.CodeParser") as MockParser,
        patch("app.services.ingest_service.Chroma"),
    ):
        MockParser.return_value.scan.return_value = ([], [])
        MockParser.return_value.persist_manifest.return_value = None

        from app.services.ingest_service import IngestionService

        svc = IngestionService(persist_directory=str(tmp_path))
        await svc.ingest_codebase(ws, mock_db)

    mock_db.update_workspace_status.assert_called_with(ws.id, WorkspaceStatus.IDLE)


async def test_ingest_counts_removed_files(tmp_path: object) -> None:
    ws = _make_workspace(tmp_path)
    mock_db = AsyncMock(spec=DatabaseService)

    with (
        patch("app.services.ingest_service.CodeParser") as MockParser,
        patch("app.services.ingest_service.Chroma") as MockChroma,
    ):
        MockParser.return_value.scan.return_value = ([], ["/old/file.py", "/old/util.py"])
        MockParser.return_value.persist_manifest.return_value = None
        mock_vs = MagicMock()
        mock_vs.delete = MagicMock()
        MockChroma.return_value = mock_vs

        from app.services.ingest_service import IngestionService

        svc = IngestionService(persist_directory=str(tmp_path))
        result = await svc.ingest_codebase(ws, mock_db)

    assert result["files_removed"] == 2
    assert result["files_processed"] == 0
