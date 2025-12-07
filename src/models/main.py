from __future__ import annotations

import argparse
import asyncio
from typing import Any

from RAG import PERSIST_DIR as DEFAULT_PERSIST_DIR
from workflow import (
    DIRECT_MODE,
    DEFAULT_K_TOOLS,
    DEFAULT_TOP_SERVERS,
    add_direct_answer_option,
    derive_mcp_url,
    execute_agent_workflow,
    rag_search,
)


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
    results = add_direct_answer_option(
        rag_search(
            args.query,
            catalog_path=args.catalog,
            top_servers=args.top_servers,
            k_tools=args.k_tools,
            force_reindex=args.reindex,
            persist_dir=args.persist_dir,
        )
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

    if chosen.get("mode") == DIRECT_MODE or not child_link:
        print("\nUsing direct answer mode (no MCP tools).")
        envelope = await execute_agent_workflow(
            notion_instruction=notion_instruction,
            child_link=None,
            server_name=server_name,
            include_raw_payload=False,
            mode=DIRECT_MODE,
        )
    else:
        try:
            mcp_url = derive_mcp_url(child_link)
        except ValueError as exc:
            print(f"Unable to derive MCP URL: {exc}")
            return
        print(f"\nUsing server '{server_name}' with MCP endpoint: {mcp_url}")

        envelope = await execute_agent_workflow(
            notion_instruction=notion_instruction,
            child_link=child_link,
            server_name=server_name,
            include_raw_payload=False,
        )
    final_output = envelope.final_output

    print("\n=== Agent Output ===\n")
    print(final_output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a RAG search, select a Smithery MCP server, and execute the task."
    )
    parser.add_argument(
        "query",
        help="Natural language query used for the RAG search (and default agent instruction).",
    )
    parser.add_argument(
        "--notion-instruction",
        help="Explicit instruction to send to the selected MCP agent (defaults to the query).",
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
