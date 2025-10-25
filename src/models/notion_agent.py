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
import os
import sys
from typing import Optional
from urllib.parse import urlencode

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


async def run_notion_task(
    user_request: str,
    *,
    notion_mcp_base_url: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required.")

    notion_url = build_smithery_notion_url(notion_mcp_base_url)

    print(f"\nConnected MCP server: {notion_url}")
    prompt = (
        "Describe exactly what you want the Notion agent to do.\n"
        "Press Enter to reuse the previous instruction: "
    )
    clarified_request = input(prompt).strip()
    task_instruction = clarified_request or user_request

    agent = build_agent(notion_url, parent_id)

    async with agent.mcp_servers[0]:
        result = await Runner.run(agent, task_instruction)
    return str(getattr(result, "final_output", result))


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
