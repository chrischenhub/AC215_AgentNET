"""Bridge utilities for interacting with the Notion MCP server via OpenAI Agents SDK."""
from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

try:  # pragma: no cover - import guard
    from agents import Agent, Runner
    from agents.mcp import MCPServerStreamableHttp, MCPServerSse
    from agents.model_settings import ModelSettings
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "openai-agents package is required. Install `openai-agents>=0.1.0` to use the Notion MCP bridge."
    ) from exc


NOTION_MCP_URL = os.getenv("NOTION_MCP_URL", "https://mcp.notion.com/mcp")
NOTION_SSE_URL = os.getenv("NOTION_SSE_URL", "https://mcp.notion.com/sse")
NOTION_MCP_AUTH = os.getenv("NOTION_MCP_AUTH")
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT_SECONDS", "30"))


def _build_headers() -> Dict[str, str]:
    if NOTION_MCP_AUTH:
        return {"Authorization": f"Bearer {NOTION_MCP_AUTH}"}
    return {}


async def connect_notion_server():
    """Return a connected Notion MCP server using Streamable HTTP with SSE fallback."""
    headers = _build_headers()

    async def _connect_streamable():
        params = {"url": NOTION_MCP_URL, "timeout": MCP_TIMEOUT}
        if headers:
            params["headers"] = headers
        server = MCPServerStreamableHttp(
            name="Notion",
            params=params,
            cache_tools_list=True,
            max_retry_attempts=3,
        )
        try:
            await server.connect()
            setattr(server, "agentnet_transport", "streamable_http")
            return server
        except Exception:
            # Ensure partially opened connections are closed before fallback
            with contextlib.suppress(Exception):
                await server.close()
            raise

    async def _connect_sse():
        params = {"url": NOTION_SSE_URL}
        if headers:
            params["headers"] = headers
        params["timeout"] = MCP_TIMEOUT
        server = MCPServerSse(
            name="Notion (SSE)",
            params=params,
            cache_tools_list=True,
            max_retry_attempts=3,
        )
        await server.connect()
        setattr(server, "agentnet_transport", "sse")
        return server

    try:
        return await _connect_streamable()
    except Exception as exc:
        sys.stderr.write(f"[warn] Streamable HTTP connection failed ({exc}); falling back to SSE.\n")
        return await _connect_sse()


async def run_notion_task(user_input: str) -> str:
    """Execute a user task against Notion MCP via the Agents SDK and return final output."""
    server = await connect_notion_server()
    async with server:
        agent = Agent(
            name="Assistant",
            instructions="Use Notion MCP tools when needed.",
            mcp_servers=[server],
            model_settings=ModelSettings(tool_choice="auto"),
        )
        try:
            result = await Runner.run(agent, user_input)
        except Exception as exc:
            raise RuntimeError(f"Notion MCP run failed: {exc}") from exc
        final_output = getattr(result, "final_output", None)
        if final_output is None:
            raise RuntimeError("Runner completed without a final output from Notion MCP.")
        return final_output


if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]).strip()
    if not user_input:
        user_input = "List available tools"
    try:
        print(asyncio.run(run_notion_task(user_input)))
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # pragma: no cover - CLI helper
        sys.stderr.write(f"Failed to run Notion MCP task: {exc}\n")
        with contextlib.suppress(Exception):
            asyncio.get_event_loop().close()
