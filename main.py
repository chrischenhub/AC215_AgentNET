from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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


def _similarity_from_score(score: Optional[float]) -> Optional[float]:
    if score is None:
        return None
    try:
        value = 1.0 - float(score)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, value))


def _truncate(text: str, limit: int = 400) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _build_reason_for_agent(query: str, metadata: Dict[str, Any], document: str) -> Optional[str]:
    if not query:
        return None
    caps_list = _metadata_to_list(metadata.get("capabilities", []))
    tags_list = _metadata_to_list(metadata.get("tags", []))
    agent_stub = {
        "name": metadata.get("name", ""),
        "description": document,
        "capabilities": caps_list,
        "tags": tags_list,
    }
    return build_reason(query, agent_stub)


def _build_agent_meta(metadata: Dict[str, Any], document: str, score: Optional[float], reason: Optional[str]) -> Dict[str, Any]:
    similarity = _similarity_from_score(score)
    snippet = _truncate(document)
    agent_meta: Dict[str, Any] = {
        "id": metadata.get("id"),
        "name": metadata.get("name"),
        "provider": metadata.get("provider"),
        "endpoint": metadata.get("endpoint"),
        "capabilities": metadata.get("capabilities", []),
        "tags": metadata.get("tags", []),
        "description": metadata.get("description") or document,
        "document": document,
        "search_snippet": snippet,
    }
    if similarity is not None:
        agent_meta["similarity"] = similarity
    if reason:
        agent_meta["reason"] = reason
    return agent_meta


def _fetch_agent_by_id(vectorstore: Chroma, agent_id: str) -> Optional[Dict[str, Any]]:
    include = {"include": ["metadatas", "documents"]}
    record: Optional[Dict[str, Any]] = None
    try:
        record = vectorstore.get(ids=[agent_id], **include)
    except TypeError:
        record = vectorstore.get(ids=[agent_id])
    except AttributeError:
        collection = getattr(vectorstore, "_collection", None)
        if collection is not None:
            record = collection.get(ids=[agent_id], **include)
    except Exception as exc:
        sys.stderr.write(f"Failed to retrieve agent '{agent_id}': {exc}\n")
        return None
    if not record:
        return None
    ids = record.get("ids") or []
    if not ids:
        return None
    metadatas = record.get("metadatas") or [{}]
    documents = record.get("documents") or [""]
    return {
        "metadata": metadatas[0] or {},
        "document": documents[0] or "",
    }


def _select_agent(vectorstore: Chroma, query: str, agent_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if agent_id:
        fetched = _fetch_agent_by_id(vectorstore, agent_id)
        if not fetched:
            return None
        metadata = fetched["metadata"]
        document = fetched["document"]
        reason = _build_reason_for_agent(query, metadata, document)
        return _build_agent_meta(metadata, document, score=None, reason=reason)
    try:
        results = vectorstore.similarity_search_with_score(query, k=3)
    except Exception as exc:
        sys.stderr.write(f"Search failed: {exc}\n")
        return None
    if not results:
        return None
    doc, score = results[0]
    metadata = doc.metadata or {}
    document = doc.page_content or ""
    reason = _build_reason_for_agent(query, metadata, document)
    return _build_agent_meta(metadata, document, score=score, reason=reason)


def _pretty_print_agent(agent_meta: Dict[str, Any]) -> None:
    agent_name = agent_meta.get("name") or "<unknown>"
    agent_id = agent_meta.get("id") or "<unknown>"
    provider = agent_meta.get("provider")
    print(f"Selected agent: {agent_name} (id={agent_id})")
    if provider:
        print(f"Provider: {provider}")
    similarity = agent_meta.get("similarity")
    if isinstance(similarity, (float, int)):
        print(f"Similarity: {float(similarity):.3f}")
    reason = agent_meta.get("reason")
    if isinstance(reason, str) and reason:
        print(reason)
    snippet = agent_meta.get("search_snippet")
    if isinstance(snippet, str) and snippet:
        print("Snippet:")
        print(snippet)


def _act(query: str, agent_id: Optional[str], dry_run: bool) -> None:
    _ensure_api_key()
    vectorstore = get_vectorstore()
    agent_meta = _select_agent(vectorstore, query, agent_id)
    if not agent_meta:
        print("No suitable agent found.")
        sys.exit(1)

    _pretty_print_agent(agent_meta)

    runner = ActRunner()
    try:
        result = runner.run(query, agent_meta, dry_run=dry_run)
    except Exception as exc:
        sys.stderr.write(f"Act execution failed: {exc}\n")
        sys.exit(1)

    if result.get("dry_run"):
        if "planned_args" in result:
            tool_name = result.get("tool") or "<unknown>"
            print(f"Planned tool: {tool_name}")
            print("Planned arguments:")
            print(json.dumps(result.get("planned_args", {}), indent=2, ensure_ascii=False))
        elif "tools" in result:
            tools = result.get("tools") or []
            print("Discovered Notion tools:")
            print(json.dumps(tools, indent=2, ensure_ascii=False))
        return

    if "final_output" in result:
        print("Final output:")
        print(result["final_output"])
        #return

    tool_name = result.get("tool") or "<unknown>"
    print(f"Executed tool: {tool_name}")
    page_url = result.get("page_url")
    if page_url:
        print(f"Page URL: {page_url}")
    page_id = result.get("page_id")
    if page_id:
        print(f"Page ID: {page_id}")
    print("Tool result:")
    print(json.dumps(result.get("result", {}), indent=2, ensure_ascii=False))


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

    act_parser = subparsers.add_parser("act", help="Plan and execute a task via a selected agent")
    act_parser.add_argument("--q", required=True, help="User task, e.g., 'Create a data structure study plan for me'")
    act_parser.add_argument("--agent-id", help="Explicit agent id to use (optional)")
    act_parser.add_argument("--dry-run", action="store_true", help="Plan only, do not execute tools")

    args = parser.parse_args()
    if args.command == "ingest":
        _ingest(args.json)
    elif args.command == "search":
        _search(args.q)
    elif args.command == "act":
        _act(args.q, agent_id=args.agent_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
