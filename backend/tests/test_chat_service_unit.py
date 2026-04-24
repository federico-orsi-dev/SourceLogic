"""Unit tests for ChatService using injected doubles — no OpenAI or ChromaDB required."""

from __future__ import annotations

import types
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.chat_service import ChatService
from sqlalchemy.ext.asyncio import AsyncSession


def _make_doc(content: str, file_path: str = "/app/main.py") -> Any:
    doc = types.SimpleNamespace()
    doc.page_content = content
    doc.metadata = {
        "file_path": file_path,
        "file_name": "main.py",
        "line_start": 1,
        "file_extension": ".py",
        "workspace_id": 1,
        "tenant_id": "t",
    }
    return doc


async def _aiter(*items: Any) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


@pytest.fixture()
def mock_vectorstore() -> MagicMock:
    vs = MagicMock()
    retriever = AsyncMock()
    retriever.ainvoke = AsyncMock(return_value=[_make_doc("def foo(): pass")])
    vs.as_retriever.return_value = retriever
    return vs


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    return session


async def test_stream_answer_emits_citations(
    mock_db_session: AsyncMock,
    mock_vectorstore: MagicMock,
) -> None:
    chunk_stop = types.SimpleNamespace(content="")
    chunk_hello = types.SimpleNamespace(content="Hello")
    chunk_world = types.SimpleNamespace(content=" world")

    mock_llm = MagicMock()
    mock_llm.astream = MagicMock(return_value=_aiter(chunk_hello, chunk_world, chunk_stop))

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        svc = ChatService(db_session=mock_db_session, vectorstore=mock_vectorstore)
        with patch.object(svc, "_create_llm", return_value=mock_llm):
            events = [
                e
                async for e in svc.stream_answer(
                    query="what is foo?",
                    session_id=1,
                    workspace_id=1,
                    tenant_id="t",
                    model="gpt-4o",
                )
            ]

    types_ = [e["type"] for e in events]
    assert "citations" in types_
    assert "token" in types_


async def test_stream_answer_token_content(
    mock_db_session: AsyncMock,
    mock_vectorstore: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.astream = MagicMock(
        return_value=_aiter(
            types.SimpleNamespace(content="Hello"),
            types.SimpleNamespace(content=" world"),
        )
    )

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        svc = ChatService(db_session=mock_db_session, vectorstore=mock_vectorstore)
        with patch.object(svc, "_create_llm", return_value=mock_llm):
            events = [
                e
                async for e in svc.stream_answer(
                    query="hi",
                    session_id=1,
                    workspace_id=1,
                    tenant_id="t",
                    model="gpt-4o",
                )
            ]

    tokens = "".join(e["token"] for e in events if e["type"] == "token")
    assert tokens == "Hello world"


async def test_stream_answer_no_api_key(mock_db_session: AsyncMock) -> None:
    vs = MagicMock()
    with patch("app.services.chat_service.settings") as mock_settings:
        mock_settings.OPENAI_API_KEY = None
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            ChatService(db_session=mock_db_session, vectorstore=vs)


async def test_citations_contain_file_metadata(
    mock_db_session: AsyncMock,
    mock_vectorstore: MagicMock,
) -> None:
    mock_llm = MagicMock()
    mock_llm.astream = MagicMock(return_value=_aiter())

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        svc = ChatService(db_session=mock_db_session, vectorstore=mock_vectorstore)
        with patch.object(svc, "_create_llm", return_value=mock_llm):
            events = [
                e
                async for e in svc.stream_answer(
                    query="q",
                    session_id=1,
                    workspace_id=1,
                    tenant_id="t",
                    model="gpt-4o",
                )
            ]

    citation_events = [e for e in events if e["type"] == "citations"]
    assert len(citation_events) == 1
    citations = citation_events[0]["citations"]
    assert len(citations) == 1
    assert citations[0]["file_name"] == "main.py"
    assert citations[0]["extension"] == ".py"
