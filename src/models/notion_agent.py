#!/usr/bin/env python3
"""
Connect an OpenAI Agent to the Notion MCP server hosted by Smithery (Streamable HTTP),
then let the agent decide to call the MCP tools to fulfill user requests.

Usage:
  # basic:
  OPENAI_API_KEY=... SMITHERY_API_KEY=... python notion_agent.py \
      "Create a page called 'Data Structures Study Plan' with sections: Arrays, Linked Lists, Trees, Graphs, Hash Tables."

  # optional parent page/database:
  OPENAI_API_KEY=... SMITHERY_API_KEY=... NOTION_PARENT_ID=xxxxxxxxxxxxxxxxxxxxxxxx python notion_agent.py \
      "Create a page called 'Data Structures Study Plan'..."

Environment variables:
  - OPENAI_API_KEY       : Your OpenAI API key.
  - SMITHERY_API_KEY     : Your Smithery API key for the hosted Notion MCP.
  - NOTION_PARENT_ID     : (optional) A Notion Page ID or Database ID to use as the default parent.
  - NOTION_MCP_BASE_URL  : (optional) Override Smithery URL; defaults to https://server.smithery.ai/notion/mcp
  - OPENAI_MODEL         : (optional) Model id; defaults to 'openai:gpt-4o'
"""

import argparse
import asyncio
import dataclasses
import os
import sys
from typing import Any, Optional
from urllib.parse import urlencode, urlparse, urlunparse

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from agents.model_settings import ModelSettings

DEFAULT_NOTION_MCP_BASE_URL = "https://server.smithery.ai/notion/mcp"


def build_smithery_notion_url(
    base_url: Optional[str] = None,
    smithery_api_key: Optional[str] = None,
) -> str:
    """
    Construct the Streamable HTTP URL to Smithery's hosted Notion MCP.
    Smithery commonly uses a query string with an api_key; keep it simple by default.
    """
    resolved_base_url = base_url or os.environ.get("NOTION_MCP_BASE_URL", DEFAULT_NOTION_MCP_BASE_URL)
    smithery_api_key = smithery_api_key or os.environ.get("SMITHERY_API_KEY")
    if not smithery_api_key:
        raise RuntimeError("SMITHERY_API_KEY is required.")
    params = {"api_key": smithery_api_key}

    # If your Smithery setup expects additional parameters (e.g., profile/config),
    # you can extend the query params here. For many setups, api_key alone is sufficient.
    return f"{resolved_base_url}?{urlencode(params)}"


def build_agent(notion_url: str, parent_id: str | None) -> Agent:
    """
    Create an Agent that knows how to use the Notion MCP tools when the task requires it.
    We keep tool choice 'auto' so the model decides when to call a tool.
    """
    # Model id: keep it explicit; you can override via OPENAI_MODEL.
    model_id = os.environ.get("OPENAI_MODEL", "gpt-5")

    # Strategic system prompt so the model reaches for Notion tools when appropriate.
    instructions = [
        "You are a Notion automation agent.",
        "When the user asks for anything in Notion (create a page, update content, add blocks, etc.),",
        "prefer calling the Notion MCP tools exposed by the connected server.",
    ]
    if parent_id:
        instructions.append(
            f"If a parent page/database id is needed, use this default unless the user specifies otherwise: {parent_id}."
        )

    # Build the MCP server (Streamable HTTP) for Smithery’s hosted Notion MCP.
    # See: Agents SDK docs – Streamable HTTP MCP servers via MCPServerStreamableHttp.  # noqa
    # https://openai.github.io/openai-agents-python/mcp/
    server = MCPServerStreamableHttp(
        name="Notion (Smithery Streamable HTTP)",
        params={"url": notion_url},
        cache_tools_list=True,
        max_retry_attempts=3,
    )

    # IMPORTANT: we add the server to `mcp_servers`, which “saves”/registers it on the agent so the model can call its tools.
    return Agent(
        name="NotionAssistant",
        model=model_id,
        instructions=" ".join(instructions),
        mcp_servers=[server],
        # Let the model decide when to call tools; switch to "required" to force tool use every turn.
        model_settings=ModelSettings(tool_choice="auto"),
    )


def sanitize_notion_url_for_logs(url: str) -> str:
    """
    Ensure we never leak sensitive Smithery API keys when echoing the MCP URL.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url
    masked_query = "api_key=***"
    return urlunparse(parsed._replace(query=masked_query))


def resolve_instruction(
    user_request: str,
    *,
    clarified_request: Optional[str],
    interactive: Optional[bool],
    notion_url: str,
) -> str:
    should_prompt = interactive
    if should_prompt is None:
        should_prompt = clarified_request is None and sys.stdin.isatty()

    if should_prompt:
        masked_url = sanitize_notion_url_for_logs(notion_url)
        print(f"\nConnected MCP server: {masked_url}")
        prompt = (
            "Describe exactly what you want the Notion agent to do.\n"
            "Press Enter to reuse the previous instruction: "
        )
        clarified = input(prompt).strip()
        return clarified or user_request

    if clarified_request:
        return clarified_request.strip() or user_request
    return user_request


def coerce_final_output(result: Any) -> str:
    value = getattr(result, "final_output", result)
    return str(value)


def serialize_agent_result(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, list):
        return [serialize_agent_result(item) for item in obj]
    if isinstance(obj, dict):
        return {str(key): serialize_agent_result(val) for key, val in obj.items()}
    if dataclasses.is_dataclass(obj):
        return {
            field.name: serialize_agent_result(getattr(obj, field.name))
            for field in dataclasses.fields(obj)
        }
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
        except TypeError:
            dumped = model_dump(mode="json")
        return serialize_agent_result(dumped)
    if hasattr(obj, "__dict__"):
        return {
            key: serialize_agent_result(val)
            for key, val in obj.__dict__.items()
            if not key.startswith("_")
        }
    return str(obj)


async def run_notion_task(
    user_request: str,
    *,
    notion_mcp_base_url: Optional[str] = None,
    parent_id: Optional[str] = None,
    clarified_request: Optional[str] = None,
    interactive: Optional[bool] = None,
    return_full: bool = False,
) -> Any:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required.")

    notion_url = build_smithery_notion_url(notion_mcp_base_url)

    task_instruction = resolve_instruction(
        user_request,
        clarified_request=clarified_request,
        interactive=interactive,
        notion_url=notion_url,
    )

    agent = build_agent(notion_url, parent_id)

    async with agent.mcp_servers[0]:
        result = await Runner.run(agent, task_instruction)

    final_output = coerce_final_output(result)
    if not return_full:
        return final_output
    return {
        "final_output": final_output,
        "raw_output": serialize_agent_result(result),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call the Notion MCP via Smithery using the OpenAI Agents SDK."
    )
    parser.add_argument(
        "user_request",
        help="Instruction for the Notion agent to execute.",
    )
    parser.add_argument(
        "--url",
        dest="notion_mcp_base_url",
        help="Override the Smithery Notion MCP base URL.",
    )
    return parser.parse_args(argv)


async def main_async(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    parent_id = os.environ.get("NOTION_PARENT_ID")
    final_output = await run_notion_task(
        args.user_request,
        notion_mcp_base_url=args.notion_mcp_base_url,
        parent_id=parent_id,
    )
    print("\n=== Agent Response ===\n")
    print(final_output)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
