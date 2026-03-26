from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from backend.app.core.config import settings
from backend.app.models import Workspace, WorkspaceStatus

# Assicuriamoci di importare il parser dal servizio AI (dove lo hai spostato)
from backend.app.services.ai_service import CodeParser, SourceCodeSplitter
from langchain_community.vectorstores import Chroma

# --- FIX IMPORT: Usa langchain_core per compatibilità 0.3+ ---
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, DirectoryPath, ValidationError

if TYPE_CHECKING:
    from backend.app.services.db_service import DatabaseService


logger = logging.getLogger(__name__)


class _IngestRequest(BaseModel):
    source_path: DirectoryPath


class IngestionService:
    def __init__(self, persist_directory: str | None = None) -> None:
        self.persist_directory = persist_directory or settings.CHROMA_PATH
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        self.vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
        )
        self.splitter = SourceCodeSplitter()

    async def ingest_codebase(
        self, workspace: Workspace, db_service: DatabaseService
    ) -> dict[str, int]:
        logger.info(f"🚀 STARTING INGESTION for Workspace {workspace.id} at {workspace.root_path}")
        await db_service.update_workspace_status(workspace.id, WorkspaceStatus.INDEXING)
        try:
            _ = _IngestRequest(source_path=workspace.root_path)
        except ValidationError as exc:
            await db_service.update_workspace_status(workspace.id, WorkspaceStatus.FAILED)
            raise ValueError(f"Invalid source_path: {workspace.root_path}") from exc

        parser = CodeParser(
            root_path=workspace.root_path,
            include_extensions=getattr(workspace, "include_extensions", None),
            exclude_folders=getattr(workspace, "exclude_patterns", None),
            manifest_path=self.persist_directory,
        )

        files_processed = 0
        chunks_created = 0
        files_removed = 0

        try:
            changed_files, removed_files = parser.scan(workspace.id)

            # --- FIX: Sintassi corretta per ChromaDB ($and) ---
            for removed_path in removed_files:
                self.vectorstore.delete(
                    where={
                        "$and": [
                            {"workspace_id": workspace.id},
                            {"tenant_id": workspace.tenant_id},
                            {"file_path": removed_path},
                        ]
                    }
                )
                files_removed += 1

            for i, file_record in enumerate(changed_files, start=1):
                documents: list[Document] = []
                for chunk in self.splitter.split_file(
                    file_record.content, file_record.language, file_record.file_path
                ):
                    documents.append(
                        Document(
                            page_content=chunk.content,
                            metadata={
                                "file_path": file_record.file_path,
                                "file_name": file_record.file_name,
                                "extension": file_record.extension,
                                "file_extension": file_record.extension,
                                "line_start": chunk.line_start,
                                "workspace_id": workspace.id,
                                "tenant_id": workspace.tenant_id,
                            },
                        )
                    )

                if not documents:
                    continue

                # --- FIX: Sintassi corretta per ChromaDB ($and) ---
                # Cancelliamo i vecchi chunk di questo file prima di riscriverli
                self.vectorstore.delete(
                    where={
                        "$and": [
                            {"workspace_id": workspace.id},
                            {"tenant_id": workspace.tenant_id},
                            {"file_path": file_record.file_path},
                        ]
                    }
                )
                logger.info(f"💾 Embedding Batch {i}...")
                self.vectorstore.add_documents(documents)
                files_processed += 1
                chunks_created += len(documents)

            parser.persist_manifest()
            # self.vectorstore.persist()  <-- RIMOSSO: Non serve più nelle nuove versioni

        except Exception:  # noqa: BLE001
            await db_service.update_workspace_status(workspace.id, WorkspaceStatus.FAILED)
            logger.exception("Indexing failed for workspace %s", workspace.id)
            raise

        await db_service.update_workspace_status(workspace.id, WorkspaceStatus.IDLE)
        await db_service.update_last_indexed_at(workspace.id, datetime.utcnow())
        logger.info(
            "🏁 INGESTION COMPLETE. Processed: %s files. Chunks: %s. Removed: %s.",
            files_processed,
            chunks_created,
            files_removed,
        )
        return {
            "files_processed": files_processed,
            "chunks_created": chunks_created,
            "files_removed": files_removed,
        }
