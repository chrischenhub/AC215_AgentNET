from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pytest

import notion_agent


def test_normalize_slug_trims_and_lowercases() -> None:
    assert notion_agent._normalize_slug("  Demo-App ") == "demo-app"


def test_get_profile_returns_default_when_unknown() -> None:
    profile = notion_agent.get_profile("mystery")
    assert profile.slug == "mystery"
    assert "automation agent" in " ".join(profile.instruction_lines)


def test_build_smithery_url_appends_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = notion_agent.SmitheryMCPProfile(
        slug="test",
        display_name="Test",
        instruction_lines=["Do it."],
    )
    monkeypatch.setenv("SMITHERY_API_KEY", "secret")

    url = notion_agent.build_smithery_url(profile=profile, base_url="https://example.com/mcp?existing=1")
    assert url.startswith("https://example.com/mcp?existing=1")
    assert "api_key=secret" in url


def test_sanitize_url_for_logs_masks_querystring() -> None:
    url = "https://example.com/mcp?api_key=secret&foo=1"
    masked = notion_agent.sanitize_url_for_logs(url)
    assert masked.endswith("api_key=***")


def test_resolve_instruction_prefers_clarified_request() -> None:
    result = notion_agent.resolve_instruction(
        "original",
        clarified_request=" updated ",
        interactive=False,
        notion_url="https://example.com",
        server_label="Demo",
    )
    assert result == "updated"


def test_serialize_agent_result_handles_nested_structures() -> None:
    @dataclass
    class Sample:
        value: int

    class Wrapper:
        def __init__(self):
            self.data = Sample(2)
            self.values = [Sample(3)]

    wrapped = Wrapper()
    serialized = notion_agent.serialize_agent_result({"item": wrapped, "count": 1})
    assert serialized["count"] == 1
    assert serialized["item"]["data"]["value"] == 2
    assert serialized["item"]["values"][0]["value"] == 3


def test_resolve_parent_id_prefers_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = notion_agent.SmitheryMCPProfile(
        slug="demo",
        display_name="Demo",
        instruction_lines=["Do it."],
        parent_env_var="PARENT_ID",
    )
    monkeypatch.setenv("PARENT_ID", "from-env")
    assert notion_agent._resolve_parent_id(profile, "explicit") == "explicit"
    assert notion_agent._resolve_parent_id(profile, None) == "from-env"


@pytest.mark.asyncio
async def test_run_smithery_task_wraps_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("SMITHERY_API_KEY", "smithery")

    monkeypatch.setattr(
        notion_agent,
        "build_smithery_url",
        lambda **kwargs: "https://example.com/mcp?api_key=smithery",
    )
    monkeypatch.setattr(
        notion_agent,
        "resolve_instruction",
        lambda *args, **kwargs: "resolved instruction",
    )

    class DummyServer:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class DummyAgent:
        def __init__(self):
            self.mcp_servers = [DummyServer()]

    class DummyResult:
        def __init__(self):
            self.final_output = "ok"
            self.extra = "value"

    async def fake_run(agent, instruction):
        assert instruction == "resolved instruction"
        return DummyResult()

    monkeypatch.setattr(notion_agent, "build_agent", lambda *args, **kwargs: DummyAgent())
    monkeypatch.setattr(notion_agent.Runner, "run", staticmethod(fake_run))

    result = await notion_agent.run_smithery_task(
        "user task",
        server_slug="demo",
        server_name="Demo",
        return_full=True,
    )

    assert result["final_output"] == "ok"
    assert result["raw_output"]["extra"] == "value"
