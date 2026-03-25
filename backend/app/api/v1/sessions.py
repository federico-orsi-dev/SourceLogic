from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.api.dependencies import get_current_tenant
from backend.app.models import Message, Session, Workspace
from backend.app.schemas.message import MessageRead
from backend.app.services.chat_service import ChatService


router = APIRouter(prefix="", tags=["sessions"])


class ChatStreamFilters(BaseModel):
    include_extensions: list[str] | None = None
    exclude_folders: list[str] | None = None


class ChatStreamPayload(BaseModel):
    query: str = Field(..., min_length=1)
    workspace_id: int
    model: Literal["gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo"] = "gpt-4o"
    filters: ChatStreamFilters | None = None


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


@router.get("/sessions/{session_id}/history", response_model=list[MessageRead])
async def get_session_history(
    session_id: int, 
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> list[MessageRead]:
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    workspace = await db.get(Workspace, session.workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Session not found.")

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
    )
    return list(result.scalars().all())


@router.post("/chat/{session_id}/stream")
async def stream_chat(
    session_id: int,
    payload: ChatStreamPayload,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
) -> StreamingResponse:
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    workspace = await db.get(Workspace, payload.workspace_id)
    if not workspace or workspace.tenant_id != tenant_id or session.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    user_message = Message(session_id=session_id, role="user", content=payload.query)
    db.add(user_message)
    await db.commit()

    chat_service = ChatService(db_session=db)
    assistant_chunks: list[str] = []
    citations: list[dict[str, Any]] = []

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in chat_service.stream_answer(
                query=payload.query,
                session_id=session_id,
                workspace_id=payload.workspace_id,
                tenant_id=tenant_id,
                model=payload.model,
                filters=payload.filters.model_dump(exclude_none=True)
                if payload.filters
                else None,
            ):
                event_type = str(event.get("type", "message"))
                if event_type == "token":
                    token = str(event.get("token", ""))
                    if token:
                        assistant_chunks.append(token)
                    yield _sse_event("token", {"token": token})
                    continue

                if event_type == "citations":
                    citations.clear()
                    citations.extend(event.get("citations", []))
                    yield _sse_event("citations", {"citations": citations})
                    continue

                yield _sse_event(event_type, event)
        except Exception as exc:  # noqa: BLE001
            yield _sse_event("error", {"detail": str(exc)})
        finally:
            assistant_text = "".join(assistant_chunks).strip()
            if assistant_text:
                assistant_message = Message(
                    session_id=session_id,
                    role="bot",
                    content=assistant_text,
                    sources={"citations": citations} if citations else None,
                )
                db.add(assistant_message)
                await db.commit()
            yield _sse_event("done", {"status": "complete"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
