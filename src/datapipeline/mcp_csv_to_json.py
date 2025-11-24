"""Convert MCP server tool metadata from CSV into JSON for RAG ingestion."""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional


DEFAULT_INPUT = Path("src/datapipeline/Data/mcp_server_tools.csv")
DEFAULT_OUTPUT = Path("src/datapipeline/Data/mcp_server_tools.json")


def parse_required_flag(raw_value: Optional[str]) -> Optional[bool]:
    """Normalize the CSV-required flag to a boolean."""
    value = (raw_value or "").strip().lower()
    if not value:
        return None
    if value == "required":
        return True
    if value == "optional":
        return False
    return None


def convert_rowset(rows: Iterable[Dict[str, str]]) -> MutableMapping[str, Any]:
    """Group tools and parameters by server, ensuring unique server_ids."""
    servers: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    used_ids: set[str] = set()

    # Precompute a unique server_id per child_link (or name fallback)
    id_map: Dict[str, str] = {}
    max_id = 0
    for row in rows:
        raw_id = (row.get("server_id") or "").strip()
        child_link = (row.get("child_link") or "").strip()
        name = (row.get("server_name") or "").strip()
        key = child_link or name
        if not key:
            continue

        candidate_id: Optional[int] = None
        if raw_id.isdigit():
            candidate_id = int(raw_id)
        if candidate_id:
            max_id = max(max_id, candidate_id)
            if raw_id not in used_ids:
                id_map[key] = raw_id
                used_ids.add(raw_id)

    next_id = max_id + 1 if max_id else 1

    def assign_id(child_link: str, name: str, raw_id: str) -> str:
        nonlocal next_id
        key = child_link or name
        if key in id_map:
            return id_map[key]
        if raw_id and raw_id not in used_ids:
            id_map[key] = raw_id
            used_ids.add(raw_id)
            return raw_id
        new_id = str(next_id)
        next_id += 1
        id_map[key] = new_id
        used_ids.add(new_id)
        return new_id

    for row in rows:
        child_link = (row.get("child_link") or "").strip()
        name = (row.get("server_name") or "").strip()
        server_id = assign_id(child_link, name, (row.get("server_id") or "").strip())

        server_key = child_link or name or server_id
        if not server_key:
            continue

        server_record = servers.setdefault(
            server_key,
            {
                "server_id": server_id,
                "name": name,
                "child_link": child_link or None,
                "description": (row.get("server_description") or row.get("description") or "").strip(),
                "tools": OrderedDict(),
            },
        )

        tool_key = (row.get("tool_slug") or row.get("tool_name") or "").strip()
        if not tool_key:
            continue

        tools: "OrderedDict[str, Dict[str, Any]]" = server_record["tools"]
        tool_record = tools.setdefault(
            tool_key,
            {
                "name": (row.get("tool_name") or "").strip(),
                "slug": (row.get("tool_slug") or "").strip() or None,
                "description": (row.get("tool_description") or "").strip(),
                "parameters": [],
            },
        )

        parameter_name = (row.get("parameter_name") or "").strip()
        if parameter_name:
            tool_record["parameters"].append(
                {
                    "name": parameter_name,
                    "required": parse_required_flag(row.get("parameter_required")),
                    "type": (row.get("parameter_type") or "").strip() or None,
                    "description": (row.get("parameter_description") or "").strip() or None,
                }
            )

    # Convert the nested OrderedDicts into plain structures for JSON serialization.
    for server in servers.values():
        tools = server["tools"]
        server["tools"] = list(tools.values())
        for tool in server["tools"]:
            tool["parameters"] = [
                param for param in tool["parameters"] if any(param.values())
            ]

    return servers


def load_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read all rows from the CSV file."""
    with csv_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError("The CSV file is empty or missing headers.")
        return [dict(row) for row in reader]


def write_json(data: MutableMapping[str, Any], output_path: Path) -> None:
    """Persist the converted data in JSON format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=2)


def convert_csv_to_json(csv_path: Path, output_path: Path) -> None:
    """High-level helper that orchestrates the CSV-to-JSON conversion."""
    rows = load_rows(csv_path)
    servers = convert_rowset(rows)
    write_json(servers, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert MCP server tool metadata CSV into JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to the source CSV file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path for the generated JSON file (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    convert_csv_to_json(args.input, args.output)


if __name__ == "__main__":
    main()
