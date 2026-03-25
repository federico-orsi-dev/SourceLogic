from backend.app.models.models import Base, Message, Session, Workspace, WorkspaceStatus

ChatSession = Session
ChatMessage = Message

__all__ = [
    "Base",
    "Workspace",
    "Session",
    "Message",
    "WorkspaceStatus",
    "ChatSession",
    "ChatMessage",
]
