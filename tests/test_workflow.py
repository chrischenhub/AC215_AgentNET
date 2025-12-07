from __future__ import annotations

import asyncio

import pytest

import workflow


def test_derive_mcp_url_builds_expected_url() -> None:
    assert (
        workflow.derive_mcp_url("/server/notion")
        == "https://server.smithery.ai/notion/mcp"
    )


def test_derive_mcp_url_requires_value() -> None:
    with pytest.raises(ValueError):
        workflow.derive_mcp_url("")


def test_extract_server_slug_handles_prefix_and_trimming() -> None:
    assert workflow.extract_server_slug(" /server/demo-app/tasks ") == "demo-app"


def test_extract_server_slug_requires_value() -> None:
    with pytest.raises(ValueError):
        workflow.extract_server_slug("")


@pytest.mark.asyncio
async def test_async_rag_search_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [{"server": "demo"}]

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(workflow, "rag_search", lambda *_, **__: expected)

    result = await workflow.async_rag_search("query")
    assert expected[0] in result
    # direct answer option should be appended
    assert any(item.get("mode") == workflow.DIRECT_MODE for item in result)


@pytest.mark.asyncio
async def test_execute_mcp_workflow_wraps_agent_result(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_smithery_task(*args, **kwargs):
        return {"final_output": "done", "raw_output": {"ok": True}}

    monkeypatch.setattr(workflow, "run_smithery_task", fake_run_smithery_task)

    envelope = await workflow.execute_mcp_workflow(
        notion_instruction="do something",
        child_link="/server/demo",
        server_name="demo",
    )

    assert envelope.mcp_base_url.endswith("/demo/mcp")
    assert envelope.final_output == "done"
    assert envelope.raw_output == {"ok": True}
