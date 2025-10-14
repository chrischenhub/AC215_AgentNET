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

import os
import sys
import asyncio
from urllib.parse import urlencode

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from agents.model_settings import ModelSettings


def build_smithery_notion_url() -> str:
    """
    Construct the Streamable HTTP URL to Smithery's hosted Notion MCP.
    Smithery commonly uses a query string with an api_key; keep it simple by default.
    """
    base_url = os.environ.get("NOTION_MCP_BASE_URL", "https://server.smithery.ai/notion/mcp")
    smithery_api_key = os.environ.get("SMITHERY_API_KEY")
    if not smithery_api_key:
        raise RuntimeError("SMITHERY_API_KEY is required.")
    params = {"api_key": smithery_api_key}

    # If your Smithery setup expects additional parameters (e.g., profile/config),
    # you can extend the query params here. For many setups, api_key alone is sufficient.
    return f"{base_url}?{urlencode(params)}"


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


async def main() -> None:
    if len(sys.argv) < 2:
        print("Please provide a user request, e.g.:")
        print("  python notion_agent.py \"Create a page for 'Data Structures Study Plan' ...\"")
        sys.exit(1)

    user_request = sys.argv[1]

    # Required env
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required.")

    # Optional default parent
    parent_id = os.environ.get("NOTION_PARENT_ID")

    # Build Notion MCP URL (Smithery)
    notion_url = build_smithery_notion_url()

    # Build agent + open a managed connection to the remote MCP server
    agent = build_agent(notion_url, parent_id)

    # Use the MCP server as an async context manager so connections cleanly close.
    # The Agent SDK handles the Streamable HTTP handshake & tool listing behind the scenes.
    # (See "Streamable HTTP MCP servers" in the Agents SDK docs.)
    async with agent.mcp_servers[0]:
        result = await Runner.run(agent, user_request)
        # Result surfaces the model's final answer; tool execution happens transparently in the run.
        print("\n=== Agent Response ===\n")
        print(getattr(result, "final_output", result))


if __name__ == "__main__":
    asyncio.run(main())
