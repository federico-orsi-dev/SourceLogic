from __future__ import annotations

from pathlib import Path

import pytest
from app.services.code_parser import (
    _LANGUAGE_MAP,
    ChunkRecord,
    CodeParser,
    FileRecord,
    SourceCodeSplitter,
)

# ---------------------------------------------------------------------------
# _LANGUAGE_MAP
# ---------------------------------------------------------------------------


def test_language_map_common_extensions() -> None:
    assert _LANGUAGE_MAP[".py"] == "python"
    assert _LANGUAGE_MAP[".ts"] == "typescript"
    assert _LANGUAGE_MAP[".js"] == "javascript"
    assert _LANGUAGE_MAP[".java"] == "java"
    assert _LANGUAGE_MAP[".go"] == "go"
    assert _LANGUAGE_MAP[".rs"] == "rust"
    assert _LANGUAGE_MAP[".cs"] == "csharp"


def test_detect_language_known() -> None:
    assert CodeParser._detect_language(".py") == "python"
    assert CodeParser._detect_language(".tsx") == "typescript"
    assert _LANGUAGE_MAP[".jsx"] == "javascript"


def test_detect_language_unknown_defaults_to_text() -> None:
    assert CodeParser._detect_language(".xyz") == "text"
    assert CodeParser._detect_language("") == "text"


# ---------------------------------------------------------------------------
# CodeParser — static / pure methods
# ---------------------------------------------------------------------------


def test_is_crucial_json_known_names() -> None:
    assert CodeParser._is_crucial_json(Path("package.json")) is True
    assert CodeParser._is_crucial_json(Path("tsconfig.json")) is True
    assert CodeParser._is_crucial_json(Path("openapi.json")) is True


def test_is_crucial_json_unknown_names() -> None:
    assert CodeParser._is_crucial_json(Path("data.json")) is False
    assert CodeParser._is_crucial_json(Path("config.json")) is False


def test_normalize_extensions_adds_dot(tmp_path: Path) -> None:
    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=["py", "ts"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    assert ".py" in parser.include_extensions
    assert ".ts" in parser.include_extensions


def test_normalize_extensions_lowercase(tmp_path: Path) -> None:
    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=["PY", ".TS"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    assert ".py" in parser.include_extensions
    assert ".ts" in parser.include_extensions


def test_normalize_extensions_empty(tmp_path: Path) -> None:
    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=None,
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    assert parser.include_extensions == set()


# ---------------------------------------------------------------------------
# CodeParser — scan with real temp directory
# ---------------------------------------------------------------------------


def test_scan_returns_changed_files(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def hello():\n    pass\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def util():\n    return 1\n", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    changed, removed = parser.scan(workspace_id=1)
    assert len(changed) == 2
    assert removed == []
    names = {f.file_name for f in changed}
    assert "main.py" in names
    assert "utils.py" in names


def test_scan_skips_unchanged_files(tmp_path: Path) -> None:
    py_file = tmp_path / "main.py"
    py_file.write_text("def hello():\n    pass\n", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    parser.scan(workspace_id=1)
    parser.persist_manifest()

    # Second scan: same content, same hash — should return 0 changed files
    parser2 = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    changed, removed = parser2.scan(workspace_id=1)
    assert changed == []
    assert removed == []


def test_scan_detects_removed_files(tmp_path: Path) -> None:
    py_file = tmp_path / "temp.py"
    py_file.write_text("x = 1\n", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    parser.scan(workspace_id=1)
    parser.persist_manifest()

    py_file.unlink()

    parser2 = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    _, removed = parser2.scan(workspace_id=1)
    assert len(removed) == 1


def test_scan_excludes_subfolders(tmp_path: Path) -> None:
    excluded = tmp_path / "vendor"
    excluded.mkdir()
    (excluded / "lib.py").write_text("# vendor lib\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("# app\n", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=["vendor"],
        manifest_path=str(tmp_path),
    )
    changed, _ = parser.scan(workspace_id=1)
    names = {f.file_name for f in changed}
    assert "lib.py" not in names
    assert "app.py" in names


def test_scan_skips_minified_js(tmp_path: Path) -> None:
    (tmp_path / "bundle.min.js").write_text("var a=1;", encoding="utf-8")
    (tmp_path / "app.js").write_text("function main() {}", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".js"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    changed, _ = parser.scan(workspace_id=1)
    names = {f.file_name for f in changed}
    assert "bundle.min.js" not in names
    assert "app.js" in names


def test_file_record_fields(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text("class Svc:\n    pass\n", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    changed, _ = parser.scan(workspace_id=1)
    assert len(changed) == 1
    record = changed[0]
    assert record.file_name == "service.py"
    assert record.extension == ".py"
    assert record.language == "python"
    assert "class Svc" in record.content
    assert len(record.file_hash) == 32  # md5 hex digest


# ---------------------------------------------------------------------------
# SourceCodeSplitter
# ---------------------------------------------------------------------------


PYTHON_CODE = """\
class MyClass:
    def method_a(self):
        return 1

    def method_b(self):
        return 2


def standalone():
    pass
"""

TS_CODE = """\
export function greet(name: string): string {
    return `Hello ${name}`;
}

const arrow = async () => {
    return 42;
};

class Service {
    run() {}
}
"""


def test_splitter_python_produces_chunks() -> None:
    splitter = SourceCodeSplitter(max_chars=500)
    chunks = splitter.split_file(PYTHON_CODE, "python", "test.py")
    assert len(chunks) >= 1
    assert all(isinstance(c, ChunkRecord) for c in chunks)
    assert all(c.content.strip() for c in chunks)


def test_splitter_typescript_produces_chunks() -> None:
    splitter = SourceCodeSplitter(max_chars=500)
    chunks = splitter.split_file(TS_CODE, "typescript", "test.ts")
    assert len(chunks) >= 1


def test_splitter_empty_input_returns_empty() -> None:
    splitter = SourceCodeSplitter()
    assert splitter.split_file("", "python", "empty.py") == []


def test_splitter_respects_max_chars() -> None:
    big_code = "x = 1\n" * 1000  # 6000 chars
    splitter = SourceCodeSplitter(max_chars=200)
    chunks = splitter.split_file(big_code, "python", "big.py")
    assert all(len(c.content) <= 200 for c in chunks)


def test_splitter_line_start_is_positive() -> None:
    splitter = SourceCodeSplitter(max_chars=500)
    chunks = splitter.split_file(PYTHON_CODE, "python", "test.py")
    assert all(c.line_start >= 1 for c in chunks)


def test_splitter_chunk_records_are_frozen() -> None:
    chunk = ChunkRecord(content="x = 1", line_start=1)
    with pytest.raises(AttributeError):
        chunk.content = "y = 2"  # type: ignore[misc]


def test_file_record_is_frozen() -> None:
    record = FileRecord(
        file_path="/tmp/f.py",
        file_name="f.py",
        extension=".py",
        language="python",
        content="x=1",
        file_hash="abc123",
    )
    with pytest.raises(AttributeError):
        record.file_name = "g.py"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SourceCodeSplitter — buffer flush path (lines 304-325)
# ---------------------------------------------------------------------------


def test_splitter_flushes_buffer_when_next_block_does_not_fit() -> None:
    # Two small defs — with max_chars=20 the second def forces a flush of the first
    code = "def a():\n    pass\n\ndef b():\n    pass\n"
    splitter = SourceCodeSplitter(max_chars=20)
    chunks = splitter.split_file(code, "python", "test.py")
    assert len(chunks) >= 2
    assert all(c.line_start >= 1 for c in chunks)


# ---------------------------------------------------------------------------
# CodeParser — error / edge paths
# ---------------------------------------------------------------------------


def test_read_text_returns_none_on_unicode_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.py"
    bad_file.write_bytes(b"\xff\xfe invalid utf-8 \x80\x81")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    # _read_text should swallow UnicodeDecodeError and return None
    result = parser._read_text(bad_file)
    assert result is None


def test_scan_skips_source_map_files(tmp_path: Path) -> None:
    (tmp_path / "app.js.map").write_text("{}", encoding="utf-8")
    (tmp_path / "app.js").write_text("function x(){}", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".js"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    changed, _ = parser.scan(workspace_id=1)
    names = {f.file_name for f in changed}
    assert "app.js.map" not in names
    assert "app.js" in names


def test_persist_manifest_is_idempotent_when_clean(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")

    parser = CodeParser(
        root_path=str(tmp_path),
        include_extensions=[".py"],
        exclude_folders=None,
        manifest_path=str(tmp_path),
    )
    parser.scan(workspace_id=1)
    parser.persist_manifest()

    # Second persist without any change — should be a no-op (covers the early-return branch)
    parser.persist_manifest()
    assert parser.manifest_file.exists()
