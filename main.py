from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


COLLECTION_NAME = "agents_v1"
PERSIST_DIR = "DB/chroma_store"
EMBED_MODEL = "text-embedding-3-large"


def load_json(path: str) -> Dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    with json_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_catalog(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "mcp" in obj:
        entries = obj["mcp"] or []
        agents: List[Dict[str, Any]] = []
        for entry in entries:
            agent = entry.get("agent")
            if agent:
                agents.append(agent)
        return agents
    if "agent" in obj:
        return [obj["agent"]]
    raise ValueError("Unsupported catalog format: expected 'mcp' array or 'agent' object")


def build_doc(agent: Dict[str, Any]) -> str:
    name = agent.get("name", "")
    provider = agent.get("provider", "")
    description = agent.get("description", "")
    capabilities = ", ".join(agent.get("capabilities", []) or [])
    tags = ", ".join(agent.get("tags", []) or [])
    parts = [name, provider, description, f"capabilities: {capabilities}", f"tags: {tags}"]
    return "\n".join(part for part in parts if part)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def build_reason(query: str, agent: Dict[str, Any]) -> str:
    query_tokens = _tokenize(query)
    fields = [
        agent.get("name", ""),
        agent.get("description", ""),
        ", ".join(agent.get("capabilities", []) or []),
        ", ".join(agent.get("tags", []) or []),
    ]
    agent_tokens = set()
    for field in fields:
        agent_tokens.update(_tokenize(field))
    overlap: List[str] = []
    for token in query_tokens:
        if token in agent_tokens and token not in overlap:
            overlap.append(token)
    if not overlap:
        return "reason: no direct token overlap"
    quoted = ", ".join(f'"{token}"' for token in overlap[:5])
    return f"reason: matches {quoted}"


def get_vectorstore(persist_dir: str = PERSIST_DIR) -> Chroma:
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    return Chroma(collection_name=COLLECTION_NAME, persist_directory=persist_dir, embedding_function=embeddings)


def _ensure_api_key() -> None:
    dotenv_path = Path(".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        message = "Missing OPENAI_API_KEY. Create a .env file with OPENAI_API_KEY or export it before running."
        sys.stderr.write(message + "\n")
        sys.exit(1)


def _join_metadata(values: Iterable[Any]) -> str:
    items = [str(value).strip() for value in values if value]
    return ", ".join(items)


def _metadata_to_list(raw: Any) -> List[str]:
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(',') if item.strip()]
    if isinstance(raw, Iterable):
        return [str(item).strip() for item in raw if item]
    return []


def _persist_vectorstore(store: Chroma) -> None:
    client = getattr(store, "_client", None)
    if client and hasattr(client, "persist"):
        client.persist()


def _ingest(json_path: str) -> None:
    _ensure_api_key()
    payload = load_json(json_path)
    agents = parse_catalog(payload)
    if not agents:
        sys.stderr.write("No agents found in catalog.\n")
        sys.exit(1)

    docs = [build_doc(agent) for agent in agents]
    ids = [agent["id"] for agent in agents]
    metadatas = [
        {
            "id": agent.get("id"),
            "name": agent.get("name"),
            "provider": agent.get("provider"),
            "endpoint": agent.get("endpoint"),
            "capabilities": _join_metadata(agent.get("capabilities", []) or []),
            "tags": _join_metadata(agent.get("tags", []) or []),
        }
        for agent in agents
    ]

    vectorstore = get_vectorstore()
    vectorstore.delete(ids=ids)
    vectorstore.add_texts(texts=docs, metadatas=metadatas, ids=ids)
    _persist_vectorstore(vectorstore)


def _format_capabilities(capabilities: Iterable[str]) -> str:
    preview = [item for item in capabilities if item]
    if not preview:
        return "capabilities:"
    return "capabilities: " + ", ".join(preview[:3])


def _search(query: str) -> None:
    _ensure_api_key()
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search_with_score(query, k=3)
    if not results:
        print("No results found.")
        return

    for index, (doc, score) in enumerate(results, start=1):
        metadata = doc.metadata or {}
        similarity = max(0.0, min(1.0, 1.0 - float(score)))
        name = metadata.get("name", "")
        provider = metadata.get("provider", "")
        agent_id = metadata.get("id", "")
        endpoint = metadata.get("endpoint", "")
        caps_list = _metadata_to_list(metadata.get("capabilities", []))
        tags_list = _metadata_to_list(metadata.get("tags", []))
        reason = build_reason(query, {
            "name": name,
            "description": doc.page_content,
            "capabilities": caps_list,
            "tags": tags_list,
        })
        print(f"[{index}] {name} — {provider}  score={similarity:.3f}  (id={agent_id})")
        print(f"    {reason}")
        if endpoint:
            print(f"    endpoint: {endpoint}")
        caps_line = _format_capabilities(caps_list)
        print(f"    {caps_line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentNET search utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest agents into Chroma")
    ingest_parser.add_argument("--json", required=True, help="Path to agents JSON file")

    search_parser = subparsers.add_parser("search", help="Search the agent catalog")
    search_parser.add_argument("--q", required=True, help="Search query")

    args = parser.parse_args()
    if args.command == "ingest":
        _ingest(args.json)
    elif args.command == "search":
        _search(args.q)


if __name__ == "__main__":
    main()
