from __future__ import annotations

from pathlib import Path

import pytest
from app.schemas.payloads import ChatStreamPayload, IngestRequest
from pydantic import ValidationError


def test_ingest_request_accepts_absolute_path(tmp_path: Path) -> None:
    req = IngestRequest(path=str(tmp_path))
    assert req.path == str(tmp_path)


def test_ingest_request_rejects_relative_path() -> None:
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(path="relative/path")
    assert "absolute" in str(exc_info.value).lower()


def test_ingest_request_normalizes_extensions_adds_dot(tmp_path: Path) -> None:
    req = IngestRequest(path=str(tmp_path), include_extensions=["py", "ts"])
    assert ".py" in req.include_extensions
    assert ".ts" in req.include_extensions


def test_ingest_request_normalizes_extensions_lowercase(tmp_path: Path) -> None:
    req = IngestRequest(path=str(tmp_path), include_extensions=["PY", ".TS", "JS"])
    assert ".py" in req.include_extensions
    assert ".ts" in req.include_extensions
    assert ".js" in req.include_extensions


def test_ingest_request_skips_empty_extensions(tmp_path: Path) -> None:
    req = IngestRequest(path=str(tmp_path), include_extensions=["", "  ", ".py"])
    assert req.include_extensions == [".py"]


def test_ingest_request_default_empty_lists(tmp_path: Path) -> None:
    req = IngestRequest(path=str(tmp_path))
    assert req.exclude_patterns == []
    assert req.include_extensions == []


def test_chat_stream_payload_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        ChatStreamPayload(query="", workspace_id=1)


def test_chat_stream_payload_default_model() -> None:
    payload = ChatStreamPayload(query="What does this do?", workspace_id=1)
    assert payload.model == "gpt-4o"
    assert payload.filters is None


def test_chat_stream_payload_accepts_valid_models() -> None:
    for model in ("gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"):
        payload = ChatStreamPayload(query="hello", workspace_id=1, model=model)
        assert payload.model == model


def test_chat_stream_payload_rejects_unknown_model() -> None:
    with pytest.raises(ValidationError):
        ChatStreamPayload(query="hello", workspace_id=1, model="gpt-5")  # type: ignore[arg-type]
