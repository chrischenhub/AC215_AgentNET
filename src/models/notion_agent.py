#!/usr/bin/env python3
"""
Generic runner for Smithery-hosted MCP servers.

Originally this module only supported the Notion MCP; it now exposes a flexible
`run_smithery_task` helper that can connect to any Smithery server (e.g.,
Notion, Microsoft Learn) as long as the Smithery slug and API key are provided.

Environment variables:
  - OPENAI_API_KEY        : Required by the OpenAI Agents SDK.
  - SMITHERY_API_KEY      : Required to authenticate against Smithery endpoints.
  - NOTION_PARENT_ID      : Optional default parent when using the Notion MCP.
  - SMITHERY_MCP_BASE_URL : Optional override for the Smithery base URL.
  - OPENAI_MODEL          : Optional model override (defaults to 'gpt-5').
"""

import argparse
import asyncio
import dataclasses
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode, urlparse, urlunparse

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from agents.model_settings import ModelSettings

DEFAULT_SMITHERY_BASE_TEMPLATE = "https://server.smithery.ai/{slug}/mcp"


@dataclass(frozen=True)
class SmitheryMCPProfile:
    slug: str
    display_name: str
    instruction_lines: list[str]
    parent_env_var: str | None = None
    extra_query_params: dict[str, str] = field(default_factory=dict)

    def render_instructions(self, server_name: str, parent_id: str | None = None) -> str:
        lines = [line.format(server=server_name) for line in self.instruction_lines]
        if parent_id and self.parent_env_var:
            lines.append(
                f"If a parent identifier is required, default to {parent_id} unless the user specifies otherwise."
            )
        return " ".join(lines)


DEFAULT_GENERIC_INSTRUCTIONS = [
    "You are an automation agent for {server}.",
    "Use the connected Smithery MCP tools to fulfill the request end-to-end.",
    "Plan your work, call tools when needed, and ground answers in tool output before responding.",
]

SMITHERY_MCP_PROFILES: dict[str, SmitheryMCPProfile] = {
    "notion": SmitheryMCPProfile(
        slug="notion",
        display_name="Notion",
        instruction_lines=[
            "You are a {server} automation agent.",
            "When the user asks for anything inside {server} (create a page, update content, add blocks, etc.), prefer calling the MCP tools exposed by the connected server.",
            "Ask clarifying questions when requirements are ambiguous, then execute the requested edits before summarizing the outcome.",
        ],
        parent_env_var="NOTION_PARENT_ID",
    ),
    "microsoft-learn": SmitheryMCPProfile(
        slug="microsoft-learn",
        display_name="Microsoft Learn",
        instruction_lines=[
            "You are a documentation research assistant specialized in {server}.",
            "Use the available search/fetch tools to gather official Microsoft/Azure content before drafting an answer.",
            "Cite the documentation you retrieved, highlight key findings, and recommend follow-up steps when applicable.",
        ],
    ),
}


def _normalize_slug(server_slug: str | None) -> str:
    slug = (server_slug or "").strip().lower()
    return slug


def get_profile(server_slug: str | None) -> SmitheryMCPProfile:
    slug = _normalize_slug(server_slug) or "smithery-server"
    profile = SMITHERY_MCP_PROFILES.get(slug)
    if profile:
        return profile
    display_name = slug.replace("-", " ").title()
    return SmitheryMCPProfile(
        slug=slug,
        display_name=display_name or "Smithery MCP Server",
        instruction_lines=DEFAULT_GENERIC_INSTRUCTIONS,
    )


def build_smithery_url(
    *,
    profile: SmitheryMCPProfile,
    smithery_api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    Construct the Streamable HTTP URL to a Smithery-hosted MCP server.
    """
    resolved_api_key = smithery_api_key or os.environ.get("SMITHERY_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("SMITHERY_API_KEY is required.")

    resolved_base = (
        base_url
        or os.environ.get("SMITHERY_MCP_BASE_URL")
        or DEFAULT_SMITHERY_BASE_TEMPLATE.format(slug=profile.slug)
    )

    query_params = {"api_key": resolved_api_key, **(profile.extra_query_params or {})}
    connector = "&" if "?" in resolved_base else "?"
    return f"{resolved_base}{connector}{urlencode(query_params)}"


def build_agent(
    profile: SmitheryMCPProfile,
    *,
    notion_url: str,
    server_name: str,
    parent_id: str | None,
) -> Agent:  # pragma: no cover - constructs external Agent objects
    """
    Create an Agent that knows how to use the selected MCP tools when the task requires it.
    We keep tool choice 'auto' so the model decides when to call a tool.
    """
    # Model id: keep it explicit; you can override via OPENAI_MODEL.
    model_id = os.environ.get("OPENAI_MODEL", "gpt-5")

    instruction_text = profile.render_instructions(server_name, parent_id)

    # Build the MCP server (Streamable HTTP) for Smithery’s hosted Notion MCP.
    # See: Agents SDK docs – Streamable HTTP MCP servers via MCPServerStreamableHttp.  # noqa
    # https://openai.github.io/openai-agents-python/mcp/
    server = MCPServerStreamableHttp(
        name=f"{server_name} (Smithery Streamable HTTP)",
        params={"url": notion_url},
        cache_tools_list=True,
        max_retry_attempts=3,
    )

    # IMPORTANT: we add the server to `mcp_servers`, which “saves”/registers it on the agent so the model can call its tools.
    agent_name = f"{server_name}Assistant"
    return Agent(
        name=agent_name,
        model=model_id,
        instructions=instruction_text,
        mcp_servers=[server],
        # Let the model decide when to call tools; switch to "required" to force tool use every turn.
        model_settings=ModelSettings(tool_choice="auto"),
    )


def sanitize_url_for_logs(url: str) -> str:
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
    server_label: str,
) -> str:
    should_prompt = interactive
    if should_prompt is None:
        should_prompt = clarified_request is None and sys.stdin.isatty()

    if should_prompt:
        masked_url = sanitize_url_for_logs(notion_url)
        print(f"\nConnected MCP server ({server_label}): {masked_url}")
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


def _resolve_parent_id(
    profile: SmitheryMCPProfile,
    explicit_parent_id: Optional[str],
) -> Optional[str]:
    if explicit_parent_id:
        return explicit_parent_id
    if profile.parent_env_var:
        return os.getenv(profile.parent_env_var)
    return None


async def run_smithery_task(
    user_request: str,
    *,
    server_slug: str,
    server_name: Optional[str] = None,
    smithery_mcp_base_url: Optional[str] = None,
    parent_id: Optional[str] = None,
    clarified_request: Optional[str] = None,
    interactive: Optional[bool] = None,
    return_full: bool = False,
) -> Any:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required.")

    profile = get_profile(server_slug)
    resolved_name = server_name or profile.display_name
    notion_url = build_smithery_url(
        profile=profile,
        base_url=smithery_mcp_base_url,
    )

    resolved_parent_id = _resolve_parent_id(profile, parent_id)

    task_instruction = resolve_instruction(
        user_request,
        clarified_request=clarified_request,
        interactive=interactive,
        notion_url=notion_url,
        server_label=resolved_name,
    )

    agent = build_agent(
        profile,
        notion_url=notion_url,
        server_name=resolved_name,
        parent_id=resolved_parent_id,
    )

    async with agent.mcp_servers[0]:
        result = await Runner.run(agent, task_instruction)

    final_output = coerce_final_output(result)
    if not return_full:
        return final_output
    return {
        "final_output": final_output,
        "raw_output": serialize_agent_result(result),
    }


# Legacy wrapper retained for reference; comment out to discourage use.
# async def run_notion_task(
#     user_request: str,
#     *,
#     notion_mcp_base_url: Optional[str] = None,
#     parent_id: Optional[str] = None,
#     clarified_request: Optional[str] = None,
#     interactive: Optional[bool] = None,
#     return_full: bool = False,
# ) -> Any:
#     """
#     Backwards-compatible wrapper for legacy callers that still reference the
#     Notion-specific helper.
#     """
#
#     return await run_smithery_task(
#         user_request,
#         server_slug="notion",
#         smithery_mcp_base_url=notion_mcp_base_url,
#         parent_id=parent_id,
#         clarified_request=clarified_request,
#         interactive=interactive,
#         return_full=return_full,
#     )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call a Smithery MCP via the OpenAI Agents SDK."
    )
    parser.add_argument(
        "user_request",
        help="Instruction for the agent to execute.",
    )
    parser.add_argument(
        "--slug",
        default="notion",
        help="Smithery server slug to use (default: notion).",
    )
    parser.add_argument(
        "--url",
        dest="notion_mcp_base_url",
        help="Override the Smithery MCP base URL.",
    )
    return parser.parse_args(argv)


async def main_async(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI wrapper
    args = parse_args(argv or sys.argv[1:])
    parent_id = os.environ.get("NOTION_PARENT_ID") if args.slug == "notion" else None
    final_output = await run_smithery_task(
        args.user_request,
        server_slug=args.slug,
        smithery_mcp_base_url=args.notion_mcp_base_url,
        parent_id=parent_id,
    )
    print("\n=== Agent Response ===\n")
    print(final_output)


def main() -> None:  # pragma: no cover - CLI wrapper
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
