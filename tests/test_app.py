from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

import app
from workflow import AgentRunEnvelope


def test_index_renders_template() -> None:
    client = TestClient(app.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_api_search_returns_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app.app)

    async def fake_async_rag_search(*args, **kwargs):
        return [{"server": "demo", "child_link": "/server/demo", "score": 1.0, "why": "because"}]

    monkeypatch.setattr(app, "async_rag_search", fake_async_rag_search)

    payload = {"query": "find tools", "persist_dir": "GCB", "top_servers": 1, "k_tools": 1, "reindex": False}
    response = client.post("/api/search", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["server"] == "demo"
    assert body["notion_instruction"] == "find tools"


def test_api_execute_returns_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app.app)

    async def fake_execute_mcp_workflow(**kwargs):
        return AgentRunEnvelope(
            mcp_base_url="https://example.com/mcp",
            final_output="ok",
            raw_output={"details": True},
        )

    monkeypatch.setattr(app, "execute_mcp_workflow", fake_execute_mcp_workflow)

    payload = {"notion_instruction": "do it", "child_link": "/server/demo", "server_name": "Demo"}
    response = client.post("/api/execute", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["final_output"] == "ok"
    assert body["raw_output"]["details"] is True


def test_frontend_resets_form_before_running() -> None:
    script = Path("src/models/static/app.js").read_text()
    submit_handler = script.index('form.addEventListener("submit"')
    reset_call = script.index("form.reset();", submit_handler)
    selected_server_branch = script.index("if (selectedServer)", submit_handler)
    assert reset_call < selected_server_branch, "User input should clear before handling submission paths."
