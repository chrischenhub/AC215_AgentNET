from __future__ import annotations

import argparse
import asyncio
from typing import Any

from RAG import PERSIST_DIR as DEFAULT_PERSIST_DIR, search_servers
from notion_agent import run_notion_task

DEFAULT_TOP_SERVERS = 3
DEFAULT_K_TOOLS = 12


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


def prompt_for_selection(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Present ranked servers and ask the user to pick one.
    """
    print("\nTop RAG matches:\n")
    for idx, item in enumerate(results, start=1):
        server = item.get("server", "unknown")
        score = item.get("score")
        why = item.get("why", "")
        child_link = item.get("child_link", "")
        print(f"{idx}. {server} (score: {score})")
        print(f"   child_link: {child_link}")
        if why:
            print(f"   why: {why}")
        print()

    # Assume the user chooses a valid index; default to 1 on empty input.
    raw_choice = input(f"Select a server to use [1-{len(results)}] (default: 1): ").strip()
    try:
        choice = 1 if not raw_choice else int(raw_choice)
    except ValueError as exc:
        raise ValueError(f"Invalid selection: {raw_choice}") from exc
    if choice < 1 or choice > len(results):
        raise ValueError(f"Selection {choice} is out of range.")
    return results[choice - 1]


async def run_workflow(args: argparse.Namespace) -> None:
    results = search_servers(
        args.query,
        args.persist_dir,
        catalog_path=args.catalog,
        top_servers=args.top_servers,
        k_tools=args.k_tools,
        force_reindex=args.reindex,
    )
    if not results:
        print("No matching servers found.")
        return

    try:
        chosen = prompt_for_selection(results)
    except ValueError as exc:
        print(f"Selection error: {exc}")
        return
    server_name = chosen.get("server", "unknown")
    child_link = chosen.get("child_link", "")
    notion_instruction = args.notion_instruction or args.query

    mcp_url = derive_mcp_url(child_link)
    print(f"\nUsing server '{server_name}' with MCP endpoint: {mcp_url}")

    final_output = await run_notion_task(
        notion_instruction,
        notion_mcp_base_url=mcp_url,
    )

    print("\n=== Notion Agent Output ===\n")
    print(final_output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a RAG search, select an MCP server, and execute a Notion task."
    )
    parser.add_argument(
        "query",
        help="Natural language query used for the RAG search (and default Notion instruction).",
    )
    parser.add_argument(
        "--notion-instruction",
        help="Explicit instruction to send to the Notion agent (defaults to the query).",
    )
    parser.add_argument(
        "--persist-dir",
        default=DEFAULT_PERSIST_DIR,
        help=f"Location of the Chroma DB (default: {DEFAULT_PERSIST_DIR}).",
    )
    parser.add_argument(
        "--catalog",
        help="Optional catalog path override when rebuilding the vector store.",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force rebuild of the vector store before searching.",
    )
    parser.add_argument(
        "--top-servers",
        type=int,
        default=DEFAULT_TOP_SERVERS,
        help=f"How many servers to display (default: {DEFAULT_TOP_SERVERS}).",
    )
    parser.add_argument(
        "--k-tools",
        type=int,
        default=DEFAULT_K_TOOLS,
        help=f"Number of tool chunks to retrieve (default: {DEFAULT_K_TOOLS}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_workflow(args))


if __name__ == "__main__":
    main()
