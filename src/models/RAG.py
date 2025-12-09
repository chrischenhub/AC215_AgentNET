from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# Paths are rooted relative to this file so the service works regardless of CWD.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_mcpinfo"
DEFAULT_DESCRIPTION_PATH = DATA_DIR / "mcp_description.json"
DESCRIPTION_CANDIDATES = [
    DEFAULT_DESCRIPTION_PATH,
    DATA_DIR / "mcp_description.json",
    BASE_DIR / "Data" / "mcp_description.json",
]
PERSIST_DIR = BASE_DIR / "GCB"
CATALOG_HASH_STAMP = PERSIST_DIR / ".catalog_hash"

COLLECTION_NAME = "servers_v1"
EMBED_MODEL = "text-embedding-3-large"


@dataclass
class ServerChunk:
    server_id: str
    server_name: str
    child_link: str
    description: str
    text: str


def sanitize_description(desc: str) -> str:
    if not desc:
        return ""
    # Strip any HTML-like tags and collapse whitespace.
    desc = re.sub(r"<[^>]+>", " ", desc)
    return re.sub(r"\s+", " ", desc).strip()


def summarize_intent(desc: str, fallback: str = "General purpose server.") -> str:
    if not desc:
        return fallback
    head = re.split(r"(?<=[.!?])\s+", desc, maxsplit=1)[0] or desc
    return head[:200].strip()


def build_server_chunks(catalog_json: dict[str, Any]) -> list[ServerChunk]:
    chunks: list[ServerChunk] = []
    for srv in (catalog_json or {}).values():
        server_id = str(srv.get("server_id", "")).strip()
        server_name = (srv.get("name") or srv.get("server_name") or "").strip() or "Unknown server"
        child_link = (srv.get("child_link") or "").strip()
        raw_desc = (srv.get("description") or "").strip()
        clean_desc = sanitize_description(raw_desc)
        intent = summarize_intent(clean_desc)

        headline = f"[Server: {server_name}]"
        body = f"Use for: {intent or 'General purpose server.'}"
        detail = clean_desc if clean_desc else ""
        text = "\n".join(filter(None, [headline, body, detail]))

        chunks.append(
            ServerChunk(
                server_id=server_id,
                server_name=server_name,
                child_link=child_link,
                description=clean_desc,
                text=text,
            )
        )
    return chunks


def load_json(path: str | Path) -> dict[str, Any]:
    with open(Path(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def clear_persist_dir(persist_dir: Path) -> None:
    """
    Clear all files in the persist directory (GCB folder) before recreating embeddings.
    This ensures a clean state - the folder is completely overwritten rather than
    accumulating old embedding files.
    """
    if not persist_dir.exists():
        return

    for item in persist_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception:
            # Continue even if some files can't be deleted (e.g., permission issues)
            pass


def index_chunks(catalog_path: Path, persist_dir: Path) -> tuple[Chroma, int]:
    """
    Create embeddings for the catalog. This function:
    1. Clears all existing files in persist_dir (GCB folder) for a clean slate
    2. Creates fresh embeddings from the catalog

    When the GCB folder is mounted from Google Cloud Bucket, this ensures
    the entire folder is overwritten (not just new files added).
    """
    catalog = load_json(catalog_path)
    chunks = build_server_chunks(catalog)
    texts = [chunk.text for chunk in chunks]
    metadatas = [
        {
            "server_id": chunk.server_id,
            "server_name": chunk.server_name,
            "child_link": chunk.child_link,
        }
        for chunk in chunks
    ]

    # Clear all existing files in the persist directory for a clean overwrite
    clear_persist_dir(persist_dir)

    # Recreate the directory after clearing
    persist_dir.mkdir(parents=True, exist_ok=True)

    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    vectordb = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
    )
    if texts:
        vectordb.add_texts(texts=texts, metadatas=metadatas)
        try:
            vectordb.persist()
        except AttributeError:
            client = getattr(vectordb, "_client", None)
            if client and hasattr(client, "persist"):
                client.persist()
    return vectordb, len(texts)


def try_load_vectordb(persist_dir: Path) -> Chroma | None:
    try:
        return Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=str(persist_dir),
            embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
        )
    except Exception:
        return None


def compute_content_hash(path: Path) -> str:
    """Compute SHA-256 hash of file contents for reliable change detection."""
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ""


def read_hash_stamp(path: Path) -> str:
    try:
        return path.read_text().strip()
    except Exception:
        return ""


def write_hash_stamp(path: Path, content_hash: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content_hash)


def resolve_catalog_path(user_path: str | Path | None) -> Path:
    """
    Resolve the server description JSON path. If user_path is provided (CLI/env), it must exist.
    Otherwise fall back to common in-repo locations.
    """

    def normalize(candidate: str | Path) -> Path:
        p = Path(candidate)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        return p

    if user_path:
        candidate = normalize(user_path)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Description path not found: {candidate}")

    fallbacks = [normalize(candidate) for candidate in DESCRIPTION_CANDIDATES]
    for candidate in fallbacks:
        if candidate.exists():
            return candidate

    searched = ", ".join(str(p) for p in fallbacks)
    raise FileNotFoundError(f"No description JSON found. Searched: {searched}")


def ensure_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in your environment or .env file.")


def is_persist_dir_empty(persist_dir: Path) -> bool:
    """Check if the persist directory is empty or doesn't exist."""
    if not persist_dir.exists():
        return True
    try:
        return not any(persist_dir.iterdir())
    except Exception:
        return True


def ensure_vectordb(
    catalog_path: Path,
    persist_dir: Path = PERSIST_DIR,
    force_reindex: bool = False,
) -> Chroma:
    """
    Ensure vector DB is available. Only rebuild when:
    1. force_reindex is True
    2. The persist directory (GCB mount) is empty
    3. The catalog content hash has changed
    """
    persist_dir.mkdir(parents=True, exist_ok=True)

    current_hash = compute_content_hash(catalog_path)
    recorded_hash = read_hash_stamp(CATALOG_HASH_STAMP)

    # Only rebuild if: forced, folder is empty, or content hash changed
    folder_empty = is_persist_dir_empty(persist_dir)
    content_changed = current_hash != recorded_hash

    needs_rebuild = force_reindex or folder_empty or content_changed

    if needs_rebuild:
        vectordb, _ = index_chunks(catalog_path, persist_dir)
        write_hash_stamp(CATALOG_HASH_STAMP, current_hash)
        return vectordb

    # Try to load existing vectordb
    vectordb = try_load_vectordb(persist_dir)
    if vectordb is None:
        vectordb, _ = index_chunks(catalog_path, persist_dir)
        write_hash_stamp(CATALOG_HASH_STAMP, current_hash)
        return vectordb

    # Verify the loaded vectordb is functional
    try:
        vectordb.similarity_search("probe", k=1)
    except Exception:
        vectordb, _ = index_chunks(catalog_path, persist_dir)
        write_hash_stamp(CATALOG_HASH_STAMP, current_hash)
        return vectordb

    return vectordb


def score_and_rank_servers(
    query: str,
    vectordb: Chroma,
    k_tools: int = 12,
    top_servers: int = 5,
) -> list[dict[str, Any]]:
    docs = vectordb.similarity_search(query, k=k_tools)

    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "docs": []})
    for rank, doc in enumerate(docs, start=1):
        metadata = doc.metadata or {}
        server_name = metadata.get("server_name", "")
        if not server_name:
            continue
        weight = 1.0 / rank
        grouped[server_name]["score"] += weight
        grouped[server_name]["docs"].append(doc)

    def reason_for_server(items: list) -> str:
        lines: list[str] = []
        for doc in items[:1]:
            if doc.page_content:
                parts = doc.page_content.splitlines()
                if len(parts) >= 2:
                    intent = parts[1].replace("Use for: ", "").strip()
                    lines.append(intent)
        summary = "; ".join(line for line in lines if line)
        return textwrap.shorten(summary or "Relevant server.", width=300, placeholder="...")

    ranked = sorted(grouped.items(), key=lambda item: item[1]["score"], reverse=True)[:top_servers]
    results: list[dict[str, Any]] = []
    for server_name, bundle in ranked:
        child_link = next(
            (
                doc.metadata.get("child_link", "")
                for doc in bundle["docs"]
                if doc.metadata and doc.metadata.get("child_link")
            ),
            "",
        )
        results.append(
            {
                "server": server_name,
                "child_link": child_link,
                "score": round(bundle["score"], 4),
                "why": reason_for_server(bundle["docs"]),
            }
        )
    return results


def search_servers(
    query: str,
    persist_dir: Path = PERSIST_DIR,
    *,
    catalog_path: str | None = None,
    top_servers: int = 5,
    k_tools: int = 12,
    force_reindex: bool = False,
) -> list[dict[str, Any]]:
    """
    Run a single RAG search and return ranked servers (name + description embeddings).
    """
    load_dotenv()
    ensure_api_key()
    env_catalog = os.getenv("MCP_SERVER_DESCRIPTION_PATH")
    resolved_catalog = resolve_catalog_path(catalog_path or env_catalog)
    vectordb = ensure_vectordb(resolved_catalog, persist_dir, force_reindex=force_reindex)
    return score_and_rank_servers(
        query,
        vectordb,
        k_tools=k_tools,
        top_servers=top_servers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG CLI for building and querying the MCP server description vector store."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Embed server descriptions and persist the Chroma vector store.",
    )
    ingest_parser.add_argument(
        "--json",
        required=True,
        help="Path to the server description JSON document.",
    )
    ingest_parser.add_argument(
        "--persist-dir",
        default=str(PERSIST_DIR),
        help=f"Directory to persist the Chroma DB (default: {PERSIST_DIR}).",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Retrieve and rank servers for a natural language query.",
    )
    search_parser.add_argument(
        "--q",
        required=True,
        help="User task or intent in natural language.",
    )
    search_parser.add_argument(
        "--persist-dir",
        default=str(PERSIST_DIR),
        help=f"Directory containing the Chroma DB (default: {PERSIST_DIR}).",
    )
    search_parser.add_argument(
        "--catalog",
        help="Optional path to rebuild the store if missing or corrupt.",
    )
    search_parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force rebuild the vector store before searching.",
    )
    search_parser.add_argument(
        "--k-tools",
        type=int,
        default=12,
        help="Number of description chunks to retrieve before aggregation (default: 12).",
    )
    search_parser.add_argument(
        "--top-servers",
        type=int,
        default=5,
        help="Number of servers to return (default: 5).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "ingest":
        load_dotenv()
        ensure_api_key()
        persist_dir = Path(args.persist_dir)
        catalog_path = resolve_catalog_path(args.json)
        _, chunk_count = index_chunks(catalog_path, persist_dir)
        content_hash = compute_content_hash(catalog_path)
        write_hash_stamp(CATALOG_HASH_STAMP, content_hash)
        print(
            json.dumps(
                {
                    "collection": COLLECTION_NAME,
                    "persist_dir": str(persist_dir),
                    "chunks_indexed": chunk_count,
                    "content_hash": content_hash,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.command == "search":
        results = search_servers(
            args.q,
            Path(args.persist_dir),
            catalog_path=args.catalog,
            k_tools=args.k_tools,
            top_servers=args.top_servers,
            force_reindex=args.reindex,
        )
        output_key = "top_5_servers" if args.top_servers == 5 else "top_servers"
        print(json.dumps({output_key: results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
