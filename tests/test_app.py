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

    async def fake_execute_agent_workflow(**kwargs):
        return AgentRunEnvelope(
            mcp_base_url="https://example.com/mcp",
            final_output="ok",
            raw_output={"details": True},
        )

    monkeypatch.setattr(app, "execute_agent_workflow", fake_execute_agent_workflow)

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


def test_render_results_hides_when_locked() -> None:
    script = Path("src/models/static/app.js").read_text()
    render_fn = script.index("const renderResults = (results) => {")
    guard = script.index("if (serverLocked)", render_fn)
    hide_call = script.index("hideResultsPanel();", guard)
    early_return = script.index("return;", hide_call)
    first_results_usage = script.index("resultsList.innerHTML", render_fn)

    assert guard < hide_call < early_return < first_results_usage, "Guard should hide and return before mutating results."


def test_agent_selection_locks_results_panel() -> None:
    script = Path("src/models/static/app.js").read_text()
    run_with_index = script.index("const runAgentWithIndex = async (index) => {")
    lock_assignment = script.index("serverLocked = true;", run_with_index)
    hide_call = script.index("hideResultsPanel();", lock_assignment)
    agent_call = script.index("await runAgentWithServer", hide_call)

    assert lock_assignment < hide_call < agent_call, "Results panel should be hidden once a server is locked in."


def test_reset_chat_clears_state_and_notifies() -> None:
    script = Path("src/models/static/app.js").read_text()
    reset_fn = script.index("const resetChatContext = () => {")
    clear_conversation = script.index('conversation.innerHTML = "";', reset_fn)
    clear_history = script.index("conversationHistory = [];", clear_conversation)
    clear_results = script.index("currentResults = [];", clear_history)
    reset_server = script.index("selectedServer = null;", clear_results)
    unlock_server = script.index("serverLocked = false;", reset_server)
    show_status = script.index('showStatus("Chat cleared. Ask a new question.");', unlock_server)

    assert (
        clear_conversation
        < clear_history
        < clear_results
        < reset_server
        < unlock_server
        < show_status
    ), "Reset should clear UI/state before notifying the user."


def test_reset_button_waits_if_busy() -> None:
    script = Path("src/models/static/app.js").read_text()
    handler = script.index('resetButton.addEventListener("click"', script.index("const resetChatContext"))
    busy_guard = script.index("if (isBusy)", handler)
    warn_status = script.index(
        'showStatus("Please wait for the current run to finish before starting over.", "error");', busy_guard
    )
    return_stmt = script.index("return;", warn_status)
    call_reset = script.index("resetChatContext();", return_stmt)

    assert busy_guard < warn_status < return_stmt < call_reset, "Reset should warn and exit when a run is in progress."
