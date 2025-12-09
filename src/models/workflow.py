from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI

from RAG import PERSIST_DIR as DEFAULT_PERSIST_DIR, ensure_api_key, search_servers
from notion_agent import run_smithery_task

DEFAULT_TOP_SERVERS = 5
DEFAULT_K_TOOLS = 12
DIRECT_MODE = "direct"
DIRECT_OPTION_LABEL = "Direct Answer"


@dataclass
class AgentRunEnvelope:
    """
    Wrapper that captures the agent's final output together with the MCP base URL
    and any raw payload returned from the Agents SDK. Raw payload is kept generic
    because the SDK may evolve (pydantic models, dataclasses, primitives, etc.).
    """

    mcp_base_url: str | None
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


def add_direct_answer_option(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Append a synthetic 'direct answer' option that bypasses MCP tools.
    """
    if any(item.get("mode") == DIRECT_MODE for item in results):
        return results
    direct_entry = {
        "server": DIRECT_OPTION_LABEL,
        "child_link": "",
        "score": None,
        "why": "Skip MCP tools and answer directly.",
        "mode": DIRECT_MODE,
    }
    return list(results) + [direct_entry]


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
    results = await asyncio.to_thread(
        rag_search,
        query,
        persist_dir=persist_dir,
        catalog_path=catalog_path,
        top_servers=top_servers,
        k_tools=k_tools,
        force_reindex=force_reindex,
    )
    return add_direct_answer_option(results)


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


def _complete_direct_answer(
    instruction: str,
    *,
    history: Optional[list[dict[str, str]]] = None,
    prior_output: Optional[str] = None,
) -> AgentRunEnvelope:
    """
    Lightweight direct answer path that avoids MCP tool calls.
    """
    ensure_api_key()
    client = OpenAI()
    model_id = os.getenv("OPENAI_MODEL", "gpt-5")
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": "You are AgentNet. Answer directly. Do not call MCP tools.",
        }
    ]
    if history:
        for item in history[-10:]:
            role = item.get("role") or "user"
            content = (item.get("content") or "").strip()
            if not content:
                continue
            messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    if prior_output:
        messages.append(
            {
                "role": "system",
                "content": f"Earlier agent output to reference: {prior_output}",
            }
        )
    messages.append({"role": "user", "content": instruction})

    result = client.chat.completions.create(
        model=model_id,
        messages=messages,
    )
    try:
        content = (result.choices[0].message.content or "").strip()
    except Exception:
        content = ""

    raw_serialized = getattr(result, "model_dump", lambda: str(result))()

    return AgentRunEnvelope(
        mcp_base_url=None,
        final_output=content,
        raw_output=raw_serialized,
    )


async def execute_agent_workflow(
    *,
    notion_instruction: str,
    child_link: Optional[str],
    server_name: Optional[str] = None,
    clarified_instruction: Optional[str] = None,
    notion_mcp_base_url_override: Optional[str] = None,
    include_raw_payload: bool = True,
    mode: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    prior_output: Optional[str] = None,
) -> AgentRunEnvelope:
    """
    General entry point that supports both MCP and direct-answer modes.
    """
    should_direct = (mode == DIRECT_MODE) or not (child_link or "").strip()
    if should_direct:
        return await asyncio.to_thread(
            _complete_direct_answer,
            notion_instruction,
            history=history,
            prior_output=prior_output,
        )

    history_text = ""
    if history:
        trimmed = history[-10:]  # keep recent turns only
        lines: list[str] = []
        for item in trimmed:
            role = item.get("role", "").strip().lower()
            content = (item.get("content") or "").strip()
            if not content:
                continue
            label = "User" if role == "user" else "Assistant"
            lines.append(f"{label}: {content}")
        if lines:
            history_text = "Previous conversation:\n" + "\n".join(lines) + "\n\n"

    enriched_instruction = notion_instruction
    if history_text:
        enriched_instruction = history_text + notion_instruction

    return await execute_mcp_workflow(
        notion_instruction=enriched_instruction,
        child_link=child_link or "",
        server_name=server_name,
        clarified_instruction=clarified_instruction,
        notion_mcp_base_url_override=notion_mcp_base_url_override,
        include_raw_payload=include_raw_payload,
    )
