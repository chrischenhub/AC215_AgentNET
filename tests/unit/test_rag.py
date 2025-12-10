from __future__ import annotations

from pathlib import Path

import pytest
from unittest.mock import MagicMock

import RAG


def test_sanitize_description_strips_html() -> None:
    raw = "<p>Hello <b>world</b></p>"
    assert RAG.sanitize_description(raw) == "Hello world"


def test_summarize_intent_uses_fallback_when_missing() -> None:
    assert RAG.summarize_intent("", fallback="fallback") == "fallback"


def test_build_server_chunks_creates_text_and_metadata() -> None:
    catalog = {
        "/server/one": {
            "server_id": "srv1",
            "name": "Server One",
            "child_link": "/server/one",
            "description": "<div>Make a page.</div>",
        }
    }

    chunks = RAG.build_server_chunks(catalog)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.server_name == "Server One"
    assert "Make a page." in chunk.text
    assert chunk.child_link == "/server/one"


def test_is_persist_dir_empty_detects_chroma_files(tmp_path: Path) -> None:
    assert RAG.is_persist_dir_empty(tmp_path) is True
    chroma_file = tmp_path / "chroma-collections.parquet"
    chroma_file.write_text("data", encoding="utf-8")
    assert RAG.is_persist_dir_empty(tmp_path) is False


def test_score_and_rank_servers_orders_by_weight() -> None:
    class DummyDoc:
        def __init__(self, metadata, page_content):
            self.metadata = metadata
            self.page_content = page_content

    class DummyVectorDB:
        def __init__(self, docs):
            self._docs = docs

        def similarity_search(self, query, k):
            return self._docs[:k]

    docs = [
        DummyDoc(
            metadata={"server_name": "A", "child_link": "/server/a"},
            page_content="[Server: A]\nUse for: alpha task",
        ),
        DummyDoc(
            metadata={"server_name": "B", "child_link": "/server/b"},
            page_content="[Server: B]\nUse for: beta task",
        ),
        DummyDoc(
            metadata={"server_name": "A", "child_link": "/server/a"},
            page_content="[Server: A]\nUse for: another alpha",
        ),
    ]
    vectordb = DummyVectorDB(docs)

    ranked = RAG.score_and_rank_servers("query", vectordb, k_tools=3, top_servers=2)
    assert ranked[0]["server"] == "A"
    assert ranked[0]["child_link"] == "/server/a"
    assert "alpha task" in ranked[0]["why"]
    assert ranked[1]["server"] == "B"


def test_ensure_api_key_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        RAG.ensure_api_key()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    RAG.ensure_api_key()


def test_hashing_utilities(tmp_path: Path) -> None:
    test_file = tmp_path / "test.txt"
    test_file.write_text("content", encoding="utf-8")

    # Test compute_content_hash
    hash_val = RAG.compute_content_hash(test_file)
    assert len(hash_val) == 64  # SHA-256 hex digest length
    assert RAG.compute_content_hash(tmp_path / "nonexistent") == ""

    # Test read/write hash stamp
    stamp_file = tmp_path / ".hash"
    RAG.write_hash_stamp(stamp_file, hash_val)
    assert RAG.read_hash_stamp(stamp_file) == hash_val
    assert RAG.read_hash_stamp(tmp_path / "missing") == ""


def test_resolution_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Test fallback resolution logic is tricky without mocking BASE_DIR,
    # but we can test the explicit user path easily.
    explicit = tmp_path / "desc.json"
    explicit.touch()
    resolved = RAG.resolve_catalog_path(str(explicit))
    assert resolved.resolve() == explicit.resolve()


def test_resolution_missing() -> None:
    with pytest.raises(FileNotFoundError):
        RAG.resolve_catalog_path("/non/existent/path.json")


def test_clear_persist_dir(tmp_path: Path) -> None:
    # Setup some files and dirs
    (tmp_path / "file.txt").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").touch()

    RAG.clear_persist_dir(tmp_path)

    assert not any(tmp_path.iterdir())


def test_ensure_vectordb_reindexes_when_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock dependencies to avoid real indexing and IO
    mock_index = MagicMock(return_value=(MagicMock(), 10))
    monkeypatch.setattr(RAG, "index_chunks", mock_index)
    monkeypatch.setattr(RAG, "compute_content_hash", lambda _: "new_hash")
    monkeypatch.setattr(RAG, "read_hash_stamp", lambda _: "old_hash")
    monkeypatch.setattr(RAG, "write_hash_stamp", MagicMock())

    vectordb = RAG.ensure_vectordb(Path("catalog.json"), tmp_path)

    mock_index.assert_called_once()
    assert vectordb is not None


def test_ensure_vectordb_skips_reindex_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock clean state: matching hash, existing non-empty dir, loadable DB
    monkeypatch.setattr(RAG, "compute_content_hash", lambda _: "same_hash")
    monkeypatch.setattr(RAG, "read_hash_stamp", lambda _: "same_hash")
    monkeypatch.setattr(RAG, "is_persist_dir_empty", lambda _: False)

    mock_db = MagicMock()
    # verify_functional check
    mock_db.similarity_search.return_value = []

    monkeypatch.setattr(RAG, "try_load_vectordb", lambda _: mock_db)
    monkeypatch.setattr(RAG, "index_chunks", MagicMock(side_effect=Exception("Should not reindex")))

    vectordb = RAG.ensure_vectordb(Path("catalog.json"), tmp_path)
    assert vectordb == mock_db
