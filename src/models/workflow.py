from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from RAG import PERSIST_DIR as DEFAULT_PERSIST_DIR, search_servers
from notion_agent import run_smithery_task

DEFAULT_TOP_SERVERS = 3
DEFAULT_K_TOOLS = 12


@dataclass
class AgentRunEnvelope:
    """
    Wrapper that captures the agent's final output together with the MCP base URL
    and any raw payload returned from the Agents SDK. Raw payload is kept generic
    because the SDK may evolve (pydantic models, dataclasses, primitives, etc.).
    """

    mcp_base_url: str
    final_output: str
    raw_output: Any


def derive_mcp_url(child_link: str) -> str:
    """
    Build the Smithery MCP endpoint from a catalog child link.
    Example: /server/notion -> https://server.smithery.ai/notion/mcp
    """
    if not child_link:
        raise ValueError("Child link is required to derive the MCP URL.")

    trimmed = child_link.strip()
    if trimmed.startswith("/server"):
        trimmed = trimmed[len("/server") :]
    trimmed = trimmed.strip("/")
    if not trimmed:
        raise ValueError(f"Unable to derive MCP path from child link: {child_link}")
    return f"https://server.smithery.ai/{trimmed}/mcp"


def extract_server_slug(child_link: str) -> str:
    """
    Convert a Smithery child link (e.g. /server/notion) into its slug.
    """
    if not child_link:
        raise ValueError("Child link is required to derive the server slug.")
    trimmed = child_link.strip().strip("/")
    if trimmed.startswith("server/"):
        trimmed = trimmed[len("server/") :]
    slug = trimmed.split("/")[0].strip()
    if not slug:
        raise ValueError(f"Unable to derive server slug from child link: {child_link}")
    return slug


def rag_search(
    query: str,
    *,
    persist_dir: str = DEFAULT_PERSIST_DIR,
    catalog_path: Optional[str] = None,
    top_servers: int = DEFAULT_TOP_SERVERS,
    k_tools: int = DEFAULT_K_TOOLS,
    force_reindex: bool = False,
) -> list[dict[str, Any]]:
    """
    Run the catalog RAG search synchronously. Callers that need to avoid blocking
    an event loop should execute this function inside a thread (e.g. asyncio.to_thread).
    """
    return search_servers(
        query,
        persist_dir,
        catalog_path=catalog_path,
        top_servers=top_servers,
        k_tools=k_tools,
        force_reindex=force_reindex,
    )


async def async_rag_search(
    query: str,
    *,
    persist_dir: str = DEFAULT_PERSIST_DIR,
    catalog_path: Optional[str] = None,
    top_servers: int = DEFAULT_TOP_SERVERS,
    k_tools: int = DEFAULT_K_TOOLS,
    force_reindex: bool = False,
) -> list[dict[str, Any]]:
    """
    Async helper for contexts (like FastAPI) where the RAG search should not block.
    """
    return await asyncio.to_thread(
        rag_search,
        query,
        persist_dir=persist_dir,
        catalog_path=catalog_path,
        top_servers=top_servers,
        k_tools=k_tools,
        force_reindex=force_reindex,
    )


async def execute_mcp_workflow(
    *,
    notion_instruction: str,
    child_link: str,
    server_name: Optional[str] = None,
    clarified_instruction: Optional[str] = None,
    notion_mcp_base_url_override: Optional[str] = None,
    include_raw_payload: bool = True,
) -> AgentRunEnvelope:
    """
    Run the Notion agent task for the selected MCP server.
    `include_raw_payload=True` keeps the full agent response so the UI can render
    richer diagnostics when available.
    """

    base_url = notion_mcp_base_url_override or derive_mcp_url(child_link)
    server_slug = extract_server_slug(child_link)

    agent_result = await run_smithery_task(
        notion_instruction,
        server_slug=server_slug,
        server_name=server_name,
        smithery_mcp_base_url=base_url,
        clarified_request=clarified_instruction,
        interactive=False,
        return_full=include_raw_payload,
    )

    if include_raw_payload:
        final_output = agent_result.get("final_output", "")
        raw_output = agent_result.get("raw_output")
    else:
        final_output = str(agent_result)
        raw_output = None

    return AgentRunEnvelope(
        mcp_base_url=base_url,
        final_output=final_output,
        raw_output=raw_output,
    )
