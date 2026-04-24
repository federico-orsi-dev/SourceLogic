from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings

_EMBEDDINGS: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the module-level HuggingFace embeddings singleton.

    The model is loaded once on first call and reused for the process lifetime,
    avoiding the ~30-60 s cold-start cost on every ChatService / IngestionService
    instantiation.
    """
    global _EMBEDDINGS
    if _EMBEDDINGS is None:
        _EMBEDDINGS = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
    return _EMBEDDINGS
