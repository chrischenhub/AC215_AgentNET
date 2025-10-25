"""
Utility helpers for augmenting scraped MCP server data.

This module adds an `id` column to `Data/mcp_servers.csv`, assigning each
server a unique sequential identifier to simplify downstream lookups.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, List


PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "Data"
CSV_PATH = DATA_DIR / "mcp_servers.csv"


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def add_id_column(csv_path: Path = CSV_PATH) -> None:
    """
    Ensure the CSV contains an `id` column with unique sequential values.

    Parameters
    ----------
    csv_path : Path
        Path to the CSV file to update. Defaults to Data/mcp_servers.csv.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    rows = _read_rows(csv_path)

    if not rows:
        logger.info("No records found in %s; nothing to update.", csv_path)
        return

    original_fields = list(rows[0].keys())
    fieldnames = _build_fieldnames(original_fields)

    for index, row in enumerate(rows, start=1):
        row["id"] = str(index)

    _write_rows(csv_path, fieldnames, rows)
    logger.info("Updated %s rows with `id` column in %s", len(rows), csv_path)


def _read_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read CSV rows into a list of dictionaries."""
    with csv_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        return list(reader)


def _build_fieldnames(original_fields: Iterable[str]) -> List[str]:
    """Construct field order with `id` leading the header."""
    filtered = [field for field in original_fields if field != "id"]
    return ["id", *filtered]


def _write_rows(csv_path: Path, fieldnames: Iterable[str], rows: Iterable[Dict[str, str]]) -> None:
    """Write rows back to the CSV with the updated schema."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    add_id_column()
