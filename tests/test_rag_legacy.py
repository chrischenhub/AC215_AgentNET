from __future__ import annotations

from pathlib import Path

import pytest

import RAG_legacy


def test_sanitize_description_strips_html() -> None:
    raw = "<p>Hello <b>world</b></p>"
    assert RAG_legacy.sanitize_description(raw) == "Hello world"


def test_summarize_intent_uses_fallback_when_missing() -> None:
    assert RAG_legacy.summarize_intent("", fallback="fallback") == "fallback"


def test_build_tool_centric_chunks_creates_text_and_metadata() -> None:
    catalog = {
        "srv1": {
            "server_id": "srv1",
            "name": "Server One",
            "child_link": "/server/one",
            "tools": [
                {
                    "name": "Create Page",
                    "slug": "create-page",
                    "description": "<div>Make a page.</div>",
                    "parameters": [
                        {"name": "title", "type": "string", "required": True},
                        {"name": "body", "type": "string", "required": False},
                    ],
                }
            ],
        }
    }

    chunks = RAG_legacy.build_tool_centric_chunks(catalog)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.tool_name == "Create Page"
    assert "Make a page." in chunk.text
    assert chunk.required_params == ["title"]


def test_chroma_persist_exists_detects_chroma_files(tmp_path: Path) -> None:
    assert RAG_legacy.chroma_persist_exists(str(tmp_path)) is False
    chroma_file = tmp_path / "chroma-collections.parquet"
    chroma_file.write_text("data", encoding="utf-8")
    assert RAG_legacy.chroma_persist_exists(str(tmp_path)) is True


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
            metadata={"server_name": "A", "tool_name": "alpha", "child_link": "/server/a"},
            page_content="[Server: A]\nUse for: alpha task\nParams: none",
        ),
        DummyDoc(
            metadata={"server_name": "B", "tool_name": "beta", "child_link": "/server/b"},
            page_content="[Server: B]\nUse for: beta task\nParams: none",
        ),
        DummyDoc(
            metadata={"server_name": "A", "tool_name": "alpha-2", "child_link": "/server/a"},
            page_content="[Server: A]\nUse for: another alpha\nParams: none",
        ),
    ]
    vectordb = DummyVectorDB(docs)

    ranked = RAG_legacy.score_and_rank_servers("query", vectordb, k_tools=3, top_servers=2)
    assert ranked[0]["server"] == "A"
    assert ranked[0]["child_link"] == "/server/a"
    assert "alpha task" in ranked[0]["why"]
    assert ranked[1]["server"] == "B"


def test_ensure_api_key_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        RAG_legacy.ensure_api_key()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    RAG_legacy.ensure_api_key()
