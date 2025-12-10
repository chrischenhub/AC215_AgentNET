from __future__ import annotations

from types import SimpleNamespace

import pytest

import main
from workflow import AgentRunEnvelope


def test_prompt_for_selection_respects_user_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = [
        {"server": "one", "child_link": "/server/one", "score": 1.0},
        {"server": "two", "child_link": "/server/two", "score": 0.9},
    ]
    monkeypatch.setattr("builtins.input", lambda _: "2")
    selected = main.prompt_for_selection(choices)
    assert selected["server"] == "two"


def test_prompt_for_selection_default(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = [{"server": "one", "child_link": "/server/one", "score": 1.0}]
    monkeypatch.setattr("builtins.input", lambda _: "")
    selected = main.prompt_for_selection(choices)
    assert selected["server"] == "one"


def test_prompt_for_selection_raises_on_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = [{"server": "one", "child_link": "/server/one", "score": 1.0}]
    monkeypatch.setattr("builtins.input", lambda _: "3")
    with pytest.raises(ValueError):
        main.prompt_for_selection(choices)


@pytest.mark.asyncio
async def test_run_workflow_prints_agent_output(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    args = SimpleNamespace(
        query="do work",
        catalog=None,
        top_servers=1,
        k_tools=1,
        reindex=False,
        persist_dir="GCB",
        notion_instruction=None,
    )

    monkeypatch.setattr(
        main,
        "rag_search",
        lambda *_, **__: [{"server": "demo", "child_link": "/server/demo", "score": 0.9, "why": ""}],
    )
    monkeypatch.setattr(main, "prompt_for_selection", lambda results: results[0])

    async def fake_execute_agent_workflow(**kwargs):
        return AgentRunEnvelope(
            mcp_base_url="https://server.smithery.ai/demo/mcp",
            final_output="Agent result",
            raw_output=None,
        )

    monkeypatch.setattr(main, "execute_agent_workflow", fake_execute_agent_workflow)

    await main.run_workflow(args)
    output = capsys.readouterr().out
    assert "Agent Output" in output
    assert "Agent result" in output
