from __future__ import annotations

from pathlib import Path

import pytest

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
