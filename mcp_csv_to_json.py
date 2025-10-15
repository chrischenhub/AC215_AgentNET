"""Convert MCP server tool metadata from CSV into JSON for RAG ingestion."""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional


DEFAULT_INPUT = Path("Data/mcp_server_tools.csv")
DEFAULT_OUTPUT = Path("Data/mcp_server_tools.json")


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
    """Group tools and parameters by server."""
    servers: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    for row in rows:
        server_key = (row.get("server_name") or row.get("server_id") or "").strip()
        if not server_key:
            # Skip rows that are missing a server identifier.
            continue

        server_record = servers.setdefault(
            server_key,
            {
                "server_id": (row.get("server_id") or "").strip() or None,
                "name": (row.get("server_name") or "").strip(),
                "child_link": (row.get("child_link") or "").strip() or None,
                "description": (row.get("server_description") or row.get("description") or "").strip(),
                "tools": OrderedDict(),
            },
        )

        tool_key = (row.get("tool_slug") or row.get("tool_name") or "").strip()
        if not tool_key:
            # No tool metadata to aggregate.
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
