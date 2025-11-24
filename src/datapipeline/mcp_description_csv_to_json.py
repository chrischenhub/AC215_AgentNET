"""Convert server description CSV (id, name, child_link, description) into JSON for RAG ingestion."""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional

# Defaults point at the server description CSV that lives alongside the model data.
DEFAULT_INPUT = Path("src/models/Data/mcp_description.csv")
DEFAULT_OUTPUT = Path("src/models/Data/mcp_description.json")


def load_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read rows from the CSV."""
    with csv_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError("CSV is empty or missing headers.")
        return [dict(row) for row in reader]


def assign_id(raw_id: str, used_ids: set[str], next_id: int) -> tuple[str, int]:
    """
    Decide on a server_id. Prefer the provided numeric id when available; otherwise
    allocate the next sequential id.
    """
    value = raw_id.strip()
    if value.isdigit() and value not in used_ids:
        used_ids.add(value)
        return value, next_id

    # Allocate a new id
    while str(next_id) in used_ids:
        next_id += 1
    allocated = str(next_id)
    used_ids.add(allocated)
    return allocated, next_id + 1


def convert_rows(rows: Iterable[Dict[str, str]]) -> MutableMapping[str, Any]:
    """
    Build an ordered mapping keyed by child_link (preferred) or name. Each value contains:
      - server_id (string)
      - name
      - child_link
      - description
    """
    servers: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    used_ids: set[str] = set()
    next_id = 1

    for row in rows:
        name = (row.get("name") or "").strip()
        child_link = (row.get("child_link") or "").strip()
        description = (row.get("description") or "").strip()
        raw_id = (row.get("id") or row.get("server_id") or "").strip()

        server_id, next_id = assign_id(raw_id, used_ids, next_id)
        key = child_link or name or server_id
        if not key:
            continue

        # Deduplicate: first occurrence wins.
        if key in servers:
            continue

        servers[key] = {
            "server_id": server_id,
            "name": name,
            "child_link": child_link or None,
            "description": description,
        }

    return servers


def write_json(data: MutableMapping[str, Any], output_path: Path) -> None:
    """Persist JSON with stable ordering."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=2, ensure_ascii=False)


def convert_csv_to_json(csv_path: Path, output_path: Path) -> None:
    rows = load_rows(csv_path)
    servers = convert_rows(rows)
    write_json(servers, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert server description CSV into JSON for RAG ingestion."
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
