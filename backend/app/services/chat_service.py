from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any, Literal, cast

from backend.app.core.config import settings
from backend.app.models import Message
from langchain_community.vectorstores import Chroma

# --- MEMORIA DISABILITATA PER FIX DEPENDENCY HELL ---
# from langchain.memory import ConversationBufferWindowMemory
# ----------------------------------------------------
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class _ChatFilters(BaseModel):
    include_extensions: list[str] | None = None
    exclude_folders: list[str] | None = None


class _ChatRequest(BaseModel):
    query: str
    session_id: int
    workspace_id: int
    tenant_id: str
    model: Literal["gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"] = "gpt-4o"
    filters: _ChatFilters | None = None


class ChatService:
    def __init__(
        self,
        db_session: AsyncSession,
        persist_directory: str | None = None,
    ) -> None:
        api_key = settings.OPENAI_API_KEY

        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in the environment.")

        self.api_key = api_key
        self.db_session = db_session
        self.persist_directory = persist_directory or settings.CHROMA_PATH
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        self.vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an expert Software Architect. Use only the retrieved "
                        "code snippets to answer the latest question. "
                        "If the answer is not present in context, say so. "
                        "Do not invent details. Reference chunk IDs like [1], [2] when "
                        "you cite evidence.\n\nRetrieved Context:\n{context}"
                    ),
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

    def _create_llm(
        self, model_name: Literal["gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"]
    ) -> ChatOpenAI:
        return ChatOpenAI(model=model_name, api_key=self.api_key, streaming=True)

    async def _load_memory(self, session_id: int) -> list[BaseMessage]:
        # Load the last 20 messages to keep the context window reasonable
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp.desc())
            .limit(20)
        )
        result = await self.db_session.execute(stmt)
        messages_db = list(result.scalars().all())
        messages_db.reverse()  # chronological order

        chat_history: list[BaseMessage] = []
        for msg in messages_db:
            if msg.role == "user":
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role == "bot":
                chat_history.append(AIMessage(content=msg.content))
        return chat_history

    def _build_retriever(
        self, workspace_id: int, tenant_id: str, filters: _ChatFilters | None
    ) -> Any:
        where: dict[str, Any] = {"$and": [{"workspace_id": workspace_id}, {"tenant_id": tenant_id}]}

        if filters and filters.include_extensions:
            normalized = []
            for ext in filters.include_extensions:
                value = ext.strip().lower()
                if not value:
                    continue
                if not value.startswith("."):
                    value = f".{value}"
                normalized.append(value)
            if normalized:
                where["$and"].append({"file_extension": {"$in": normalized}})

        if filters and filters.exclude_folders:
            excludes = [folder.strip() for folder in filters.exclude_folders if folder]
            if excludes:
                where["$and"].append({"file_path": {"$nin": excludes}})

        return self.vectorstore.as_retriever(search_kwargs={"k": 5, "filter": where})

    async def stream_answer(
        self,
        query: str,
        session_id: int,
        workspace_id: int,
        tenant_id: str,
        model: str,
        filters: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        normalized_model = (
            model if model in {"gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"} else "gpt-4o"
        )
        normalized_filters = _ChatFilters.model_validate(filters) if filters is not None else None
        try:
            request = _ChatRequest(
                query=query,
                session_id=session_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                model=cast(Any, normalized_model),
                filters=normalized_filters,
            )
        except ValidationError as exc:
            raise ValueError("Invalid query, session_id, workspace_id, or model.") from exc

        chat_history = await self._load_memory(request.session_id)

        retriever = self._build_retriever(
            request.workspace_id,
            request.tenant_id,
            request.filters,
        )
        documents = await retriever.ainvoke(request.query)
        citations = self._build_citations(documents)
        context = self._build_context(documents, citations)

        yield {"type": "citations", "citations": citations}

        prompt_messages = self.prompt.format_messages(
            context=context,
            chat_history=chat_history,
            input=request.query,
        )
        llm = self._create_llm(request.model)
        async for chunk in llm.astream(prompt_messages):
            token = self._chunk_to_text(chunk)
            if token:
                yield {"type": "token", "token": token}

    def _build_citations(self, documents: list[Any]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for index, document in enumerate(documents, start=1):
            metadata = getattr(document, "metadata", {}) or {}
            citations.append(
                {
                    "chunk_id": index,
                    "file_path": metadata.get("file_path"),
                    "file_name": metadata.get("file_name"),
                    "line_start": metadata.get("line_start"),
                    "extension": metadata.get("file_extension") or metadata.get("extension"),
                }
            )
        return citations

    def _build_context(self, documents: list[Any], citations: list[dict[str, Any]]) -> str:
        if not documents:
            return "No relevant source chunks were retrieved."

        blocks: list[str] = []
        for citation, document in zip(citations, documents, strict=True):
            path = citation.get("file_path") or "unknown"
            line = citation.get("line_start") or "?"
            chunk_id = citation.get("chunk_id")
            content = getattr(document, "page_content", "")
            blocks.append(f"[{chunk_id}] {path}:{line}\n{content}")
        return "\n\n".join(blocks)

    def _chunk_to_text(self, chunk: Any) -> str:
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "".join(parts)
        return str(content or "")
