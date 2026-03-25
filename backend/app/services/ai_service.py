from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

# --- IMPORT MODERNI LANGCHAIN 0.3 (FIXED) ---
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
# --------------------------------------------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models import Message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileRecord:
    file_path: str
    file_name: str
    extension: str
    language: str
    content: str
    file_hash: str


@dataclass(frozen=True)
class ChunkRecord:
    content: str
    line_start: int


class CodeParser:
    def __init__(
        self,
        root_path: str,
        include_extensions: list[str] | None,
        exclude_folders: list[str] | None,
        manifest_path: str,
    ) -> None:
        self.root_path = Path(root_path)
        self.include_extensions = self._normalize_extensions(include_extensions)
        self.exclude_folders = set(filter(None, exclude_folders or []))
        self.manifest_file = Path(manifest_path) / "hash_manifest.json"
        self._manifest = self._load_manifest()
        self._dirty = False

    def scan(self, workspace_id: int) -> tuple[list[FileRecord], list[str]]:
        workspace_key = str(workspace_id)
        workspace_manifest = self._manifest.get(workspace_key, {})
        current_files: set[str] = set()
        changed_files: list[FileRecord] = []

        for path in self._iter_files(self.root_path):
            current_files.add(str(path))
            file_hash = self._hash_file(path)
            if not file_hash:
                continue
            if workspace_manifest.get(str(path)) == file_hash:
                continue

            content = self._read_text(path)
            if content is None:
                continue

            record = FileRecord(
                file_path=str(path),
                file_name=path.name,
                extension=path.suffix.lower(),
                language=self._detect_language(path.suffix.lower()),
                content=content,
                file_hash=file_hash,
            )
            changed_files.append(record)
            workspace_manifest[str(path)] = file_hash
            self._dirty = True

        removed_files = list(set(workspace_manifest.keys()) - current_files)
        if removed_files:
            for removed in removed_files:
                workspace_manifest.pop(removed, None)
            self._dirty = True

        self._manifest[workspace_key] = workspace_manifest
        return changed_files, removed_files

    def persist_manifest(self) -> None:
        if not self._dirty:
            return
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_file.write_text(json.dumps(self._manifest, indent=2), "utf-8")
        self._dirty = False

    def _iter_files(self, base_path: Path):
        ignored_dirs = {
            ".next", "_next", "out", "build", "dist", "static", "public",
            "coverage", "node_modules", "jspm_packages", "bower_components",
            "bin", "obj", "packages", "testresults", ".nuget", ".venv",
            "venv", "env", "__pycache__", ".pytest_cache", ".git",
            ".vscode", ".idea", ".vs",
        }

        extensions = (
            self.include_extensions
            if self.include_extensions
            else {
                ".py", ".js", ".ts", ".tsx", ".jsx", ".cs", ".java",
                ".go", ".rs", ".c", ".cpp", ".h",
            }
        )

        for root, dirs, files in base_path.walk():
            allowed_dirs: list[str] = []
            for dir_name in dirs:
                dir_path = root / dir_name
                if dir_name.lower() in ignored_dirs:
                    logger.info(f"🚫 [SKIP] Directory ignored: {dir_name}")
                    continue
                if self.exclude_folders and any(
                    token and token in str(dir_path) for token in self.exclude_folders
                ):
                    logger.info(f"🚫 [SKIP] Directory ignored: {dir_name}")
                    continue
                allowed_dirs.append(dir_name)
            dirs[:] = allowed_dirs

            for filename in files:
                path = root / filename
                skip_reason = self._skip_file_reason(path, extensions)
                if skip_reason:
                    logger.info(f"🚫 [SKIP] File ignored: {filename}")
                    continue
                logger.info(f"✅ [SCAN] Accepted: {path.name} (in {path.parent.name})")
                yield path

    def _skip_file_reason(self, path: Path, extensions: set[str]) -> str | None:
        lower_name = path.name.lower()
        extension = path.suffix.lower()

        if extension not in extensions:
            return "unsupported_extension"

        if lower_name.endswith(".map"):
            return "source_map"
        if lower_name.endswith(".min.js"):
            return "minified_js"
        if lower_name.endswith(".hot-update.js"):
            return "hot_update_bundle"
        if extension == ".json" and not self._is_crucial_json(path):
            return "non_crucial_json"
        if self.exclude_folders and any(
            token and token in str(path) for token in self.exclude_folders
        ):
            return "excluded_by_filter"

        return None

    @staticmethod
    def _is_crucial_json(path: Path) -> bool:
        crucial_json = {
            "package.json", "tsconfig.json", "tsconfig.base.json",
            "tsconfig.app.json", "tsconfig.node.json", "pyrightconfig.json",
            "openapi.json", "swagger.json", "appsettings.json",
            "appsettings.development.json",
        }
        return path.name.lower() in crucial_json

    def _read_text(self, file_path: Path) -> str | None:
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("Skipping unreadable file: %s", file_path)
            return None
        except OSError as exc:
            logger.warning("Skipping file due to OS error: %s (%s)", file_path, exc)
            return None

    def _hash_file(self, file_path: Path) -> str | None:
        try:
            hasher = hashlib.md5()
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as exc:
            logger.warning("Skipping file due to hash error: %s (%s)", file_path, exc)
            return None

    def _load_manifest(self) -> dict[str, dict[str, str]]:
        if not self.manifest_file.exists():
            return {}
        try:
            return json.loads(self.manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read manifest: %s", exc)
            return {}

    def _normalize_extensions(self, extensions: list[str] | None) -> set[str]:
        if not extensions:
            return set()
        normalized = set()
        for ext in extensions:
            value = ext.strip().lower()
            if not value:
                continue
            if not value.startswith("."):
                value = f".{value}"
            normalized.add(value)
        return normalized

    @staticmethod
    def _detect_language(extension: str) -> str:
        if extension in {".js", ".jsx"}:
            return "javascript"
        if extension in {".ts", ".tsx"}:
            return "typescript"
        return "python"


class SourceCodeSplitter:
    def __init__(self, max_chars: int = 1500) -> None:
        self.max_chars = max_chars

    def split_file(self, text: str, language: str, file_path: str) -> list[ChunkRecord]:
        blocks = self._split_by_language_blocks(text, language)
        if not blocks:
            return []

        chunks: list[ChunkRecord] = []
        buffer = ""
        buffer_start = blocks[0][0]

        for start, block in blocks:
            if not buffer:
                buffer_start = start

            if len(buffer) + len(block) <= self.max_chars:
                buffer += block
                continue

            if buffer:
                chunks.append(
                    ChunkRecord(
                        content=buffer,
                        line_start=self._line_start(text, buffer_start),
                    )
                )
                buffer = ""

            if len(block) > self.max_chars:
                offset = 0
                while offset < len(block):
                    slice_text = block[offset : offset + self.max_chars]
                    chunks.append(
                        ChunkRecord(
                            content=slice_text,
                            line_start=self._line_start(text, start + offset),
                        )
                    )
                    offset += self.max_chars
            else:
                buffer = block
                buffer_start = start

        if buffer:
            chunks.append(
                ChunkRecord(
                    content=buffer,
                    line_start=self._line_start(text, buffer_start),
                )
            )
        return chunks

    def _split_by_language_blocks(self, text: str, language: str) -> list[tuple[int, str]]:
        lines = text.splitlines(keepends=True)
        boundaries: list[int] = [0]
        offset = 0

        if language == "python":
            pattern = re.compile(r"^\s*(def|class)\s+")
        else:
            pattern = re.compile(
                r"^\s*(export\s+)?(async\s+)?(function|class)\b|^\s*(const|let|var)\s+\w+\s*=\s*(async\s*)?.*=>"
            )

        for line in lines:
            if pattern.match(line) and offset not in boundaries:
                boundaries.append(offset)
            offset += len(line)

        boundaries.append(len(text))
        boundaries = sorted(set(boundaries))

        blocks: list[tuple[int, str]] = []
        for start, end in zip(boundaries, boundaries[1:]):
            chunk = text[start:end]
            if chunk.strip():
                blocks.append((start, chunk))
        return blocks

    @staticmethod
    def _line_start(text: str, start_index: int) -> int:
        return text[:start_index].count("\n") + 1


class AIService:
    def __init__(
        self,
        db_session: AsyncSession,
        persist_directory: str | None = None,
        model_name: str = "gpt-4o",
    ) -> None:
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
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            streaming=True,
        )

    async def _load_chat_history(self, session_id: int) -> str:
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp.desc())
            .limit(5)
        )
        result = await self.db_session.execute(stmt)
        messages = list(result.scalars().all())
        history_lines = []
        for message in reversed(messages):
            role = "User" if message.role == "user" else "Assistant"
            history_lines.append(f"{role}: {message.content}")
        return "\n".join(history_lines)

    def _build_retriever(
        self,
        workspace_id: int,
        include_extensions: list[str] | None,
        exclude_folders: list[str] | None,
    ):
        where: dict[str, Any] = {"workspace_id": workspace_id}

        if include_extensions:
            normalized = []
            for ext in include_extensions:
                value = ext.strip().lower()
                if not value:
                    continue
                if not value.startswith("."):
                    value = f".{value}"
                normalized.append(value)
            if normalized:
                where = {"$and": [where, {"extension": {"$in": normalized}}]}

        if exclude_folders:
            excludes = [folder.strip() for folder in exclude_folders if folder.strip()]
            if excludes:
                where = {"$and": [where, {"file_path": {"$nin": excludes}}]}

        return self.vectorstore.as_retriever(search_kwargs={"k": 5, "filter": where})

    def _build_qa_chain(self, retriever):
        prompt = PromptTemplate(
            input_variables=["context", "input", "chat_history"],
            template=(
                "You are an expert Software Architect.\n"
                "Use the following pieces of retrieved context and the chat history to answer the user's question.\n"
                "If the answer is not in the context, clearly state that you cannot find it in the codebase.\n\n"
                "Chat History:\n{chat_history}\n\n"
                "Context:\n{context}\n\n"
                "Question: {input}\n"
                "Answer:"
            ),
        )

        combine_docs_chain = create_stuff_documents_chain(
            llm=self.llm,
            prompt=prompt,
            document_variable_name="context",
        )

        return create_retrieval_chain(
            retriever=retriever,
            combine_docs_chain=combine_docs_chain,
        )

    async def stream_answer(
        self,
        query: str,
        session_id: int,
        workspace_id: int,
        include_extensions: list[str] | None = None,
        exclude_folders: list[str] | None = None,
    ) -> AsyncIterator[str]:
        chat_history = await self._load_chat_history(session_id)
        retriever = self._build_retriever(
            workspace_id, include_extensions, exclude_folders
        )
        chain = self._build_qa_chain(retriever)

        async for chunk in chain.astream(
            {"input": query, "chat_history": chat_history}
        ):
            if "answer" in chunk:
                yield chunk["answer"]