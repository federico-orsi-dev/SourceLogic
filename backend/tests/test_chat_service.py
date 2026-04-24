from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.payloads import ChatStreamFilters
from app.services.chat_service import ChatService

# ---------------------------------------------------------------------------
# ChatStreamFilters — pure Pydantic model
# ---------------------------------------------------------------------------


def test_chat_filters_defaults() -> None:
    f = ChatStreamFilters()
    assert f.include_extensions is None
    assert f.exclude_folders is None


def test_chat_filters_with_values() -> None:
    f = ChatStreamFilters(include_extensions=[".py"], exclude_folders=["vendor"])
    assert f.include_extensions == [".py"]
    assert f.exclude_folders == ["vendor"]


# ---------------------------------------------------------------------------
# _build_citations — pure, no LLM / DB
# ---------------------------------------------------------------------------


def _make_doc(metadata: dict) -> object:  # type: ignore[type-arg]
    return SimpleNamespace(metadata=metadata, page_content="some code")


def test_build_citations_empty() -> None:
    svc = MagicMock(spec=ChatService)
    result = ChatService._build_citations(svc, [])
    assert result == []


def test_build_citations_single() -> None:
    svc = MagicMock(spec=ChatService)
    doc = _make_doc(
        {
            "file_path": "/src/app.py",
            "file_name": "app.py",
            "line_start": 10,
            "file_extension": ".py",
        }
    )
    citations = ChatService._build_citations(svc, [doc])
    assert len(citations) == 1
    assert citations[0]["chunk_id"] == 1
    assert citations[0]["file_name"] == "app.py"
    assert citations[0]["extension"] == ".py"


def test_build_citations_falls_back_to_extension_key() -> None:
    svc = MagicMock(spec=ChatService)
    doc = _make_doc({"extension": ".ts"})  # legacy key, no file_extension
    citations = ChatService._build_citations(svc, [doc])
    assert citations[0]["extension"] == ".ts"


def test_build_citations_missing_metadata() -> None:
    svc = MagicMock(spec=ChatService)
    doc = SimpleNamespace(metadata=None, page_content="x")
    citations = ChatService._build_citations(svc, [doc])
    assert citations[0]["file_path"] is None


# ---------------------------------------------------------------------------
# _build_context — pure, no LLM / DB
# ---------------------------------------------------------------------------


def test_build_context_empty_documents() -> None:
    svc = MagicMock(spec=ChatService)
    result = ChatService._build_context(svc, [], [])
    assert "No relevant" in result


def test_build_context_formats_blocks() -> None:
    svc = MagicMock(spec=ChatService)
    doc = _make_doc(
        {
            "file_path": "/src/app.py",
            "file_name": "app.py",
            "line_start": 5,
            "file_extension": ".py",
        }
    )
    citations = [{"chunk_id": 1, "file_path": "/src/app.py", "line_start": 5}]
    result = ChatService._build_context(svc, [doc], citations)
    assert "[1]" in result
    assert "/src/app.py" in result
    assert "some code" in result


def test_build_context_unknown_path() -> None:
    svc = MagicMock(spec=ChatService)
    doc = SimpleNamespace(metadata={}, page_content="content")
    citations = [{"chunk_id": 1, "file_path": None, "line_start": None}]
    result = ChatService._build_context(svc, [doc], citations)
    assert "unknown" in result
    assert "?" in result


# ---------------------------------------------------------------------------
# _chunk_to_text — pure, no LLM / DB
# ---------------------------------------------------------------------------


def test_chunk_to_text_string_content() -> None:
    svc = MagicMock(spec=ChatService)
    chunk = SimpleNamespace(content="hello world")
    assert ChatService._chunk_to_text(svc, chunk) == "hello world"


def test_chunk_to_text_list_content() -> None:
    svc = MagicMock(spec=ChatService)
    chunk = SimpleNamespace(content=["hello ", "world"])
    assert ChatService._chunk_to_text(svc, chunk) == "hello world"


def test_chunk_to_text_list_with_dict() -> None:
    svc = MagicMock(spec=ChatService)
    chunk = SimpleNamespace(content=[{"text": "hi"}, " there"])
    assert ChatService._chunk_to_text(svc, chunk) == "hi there"


def test_chunk_to_text_no_content() -> None:
    svc = MagicMock(spec=ChatService)
    chunk = SimpleNamespace(content="")
    result = ChatService._chunk_to_text(svc, chunk)
    assert result == ""


def test_chunk_to_text_non_string_content() -> None:
    svc = MagicMock(spec=ChatService)
    chunk = SimpleNamespace(content=42)
    result = ChatService._chunk_to_text(svc, chunk)
    assert result == "42"
