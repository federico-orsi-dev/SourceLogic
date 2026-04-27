from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.embeddings import get_embeddings
from langchain_community.vectorstores import Chroma


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    return Chroma(
        persist_directory=settings.CHROMA_PATH,
        embedding_function=get_embeddings(),
    )
