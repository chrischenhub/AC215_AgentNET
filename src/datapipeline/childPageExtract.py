"""
Scrape detailed MCP server tool metadata from Smithery child pages.

This script reads the server listing CSV produced by the parent scraper, visits
each server's detail page, extracts tool information (including parameters), and
stores the results in a normalized CSV suitable for database ingestion.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import re
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import HTTPError, RequestException


BASE_URL = "https://smithery.ai"
SERVERS_CSV_PATH = Path("src/datapipeline/Data/mcp_servers.csv")
OUTPUT_CSV_PATH = Path("src/datapipeline/Data/mcp_server_tools.csv")
REQUEST_PAUSE_SECONDS = 1.0
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ServerRecord:
    """Minimal metadata for a server detail scrape."""

    server_id: str
    name: str
    child_link: str


@dataclass
class ToolParameter:
    """Structured representation of a tool parameter."""

    name: str
    description: str
    param_type: Optional[str] = None
    required: Optional[bool] = None


@dataclass
class Tool:
    """Structured representation of a server tool."""

    name: str
    slug: Optional[str]
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)


def load_servers(csv_path: Path = SERVERS_CSV_PATH) -> List[ServerRecord]:
    """Load server records from the parent CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Server CSV not found at {csv_path}")

    servers: List[ServerRecord] = []
    with csv_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        for index, row in enumerate(reader, start=1):
            child_link = (row.get("child_link") or row.get("url") or "").strip()
            name = (row.get("name") or "").strip()
            server_id = (row.get("id") or str(index)).strip()

            if not child_link or not name:
                logger.warning("Skipping incomplete row: %s", row)
                continue

            servers.append(ServerRecord(server_id=server_id, name=name, child_link=child_link))

    return servers


def scrape_server_tools(session: Session, server: ServerRecord) -> List[Tool]:
    """Scrape tool metadata for a single server across paginated pages."""
    html = fetch_server_page(session, server.child_link, page=1)
    if not html:
        return []

    tools: List[Tool] = []
    total_pages = extract_total_pages(html)

    tools.extend(parse_tools_from_html(html))

    for page in range(2, total_pages + 1):
        time.sleep(REQUEST_PAUSE_SECONDS)
        next_html = fetch_server_page(session, server.child_link, page=page)
        if not next_html:
            break
        tools.extend(parse_tools_from_html(next_html))

    return tools


def fetch_server_page(session: Session, child_link: str, *, page: int) -> Optional[str]:
    """Fetch a server detail page, handling pagination via query params."""
    full_url = f"{BASE_URL}{child_link}"
    params = {}
    if page > 1:
        params.update({"capability": "tools", "page": page})

    try:
        response = session.get(full_url, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except HTTPError as exc:
        logger.error("HTTP error %s while fetching %s", exc.response.status_code, exc.response.url)
    except RequestException as exc:
        logger.error("Request error while fetching %s: %s", full_url, exc)
    return None


def extract_total_pages(html: str) -> int:
    """Inspect pagination indicator like '1 / 6' to determine total pages."""
    soup = BeautifulSoup(html, "html.parser")
    span = soup.find("span", string=re.compile(r"\d+\s*/\s*\d+"))
    if span:
        match = re.search(r"\d+\s*/\s*(\d+)", span.get_text(" ", strip=True))
        if match:
            try:
                return max(1, int(match.group(1)))
            except ValueError:
                pass
    return 1


def parse_tools_from_html(html: str) -> List[Tool]:
    """Parse tool cards from the new Smithery server detail layout."""
    soup = BeautifulSoup(html, "html.parser")
    tool_cards = soup.select("details.group.border.rounded-md")
    tools: List[Tool] = []

    for card in tool_cards:
        title_tag = card.select_one("summary h3.font-medium")
        if not title_tag:
            continue
        raw_title = normalize_text(title_tag.get_text(" ", strip=True))
        name, slug = split_tool_label(raw_title)

        desc_tag = card.select_one("summary p")
        description = normalize_text(desc_tag.get_text(" ", strip=True)) if desc_tag else ""

        parameters: List[ToolParameter] = []
        param_section = card.find("h4", string=re.compile("Parameters", re.IGNORECASE))
        if param_section:
            param_blocks = param_section.find_next("div").find_all("div", class_=lambda c: c and "space-y-2" in c)
            for block in param_blocks:
                name_tag = block.find("span", class_=lambda c: c and "text-sm" in c)
                type_tag = block.find("div", class_=lambda c: c and "inline-flex" in c)
                desc_block = block.find("p")

                if not name_tag:
                    continue

                param_name_raw = name_tag.get_text(" ", strip=True)
                required = "*required" in param_name_raw
                param_name = param_name_raw.replace("*required", "").strip()

                param_type = normalize_text(type_tag.get_text(" ", strip=True)) if type_tag else ""
                param_desc = normalize_text(desc_block.get_text(" ", strip=True)) if desc_block else ""

                parameters.append(
                    ToolParameter(
                        name=param_name,
                        description=param_desc,
                        param_type=param_type or None,
                        required=required,
                    )
                )

        tools.append(
            Tool(
                name=name,
                slug=slug,
                description=description,
                parameters=parameters,
            )
        )

    return tools


def split_tool_label(label: str) -> tuple[str, Optional[str]]:
    """Split combined tool labels into display name and slug."""
    if "(" in label and label.endswith(")"):
        name_part, slug_part = label.rsplit("(", 1)
        return name_part.strip(), slug_part[:-1].strip() or None
    return label, None


def normalize_text(value: str) -> str:
    """Collapse whitespace for cleaner CSV output."""
    return " ".join(value.split())


def flatten_records(server: ServerRecord, tools: Iterable[Tool]) -> List[Dict[str, Optional[str]]]:
    """Produce CSV-ready rows from tool data."""
    rows: List[Dict[str, Optional[str]]] = []

    for tool in tools:
        if tool.parameters:
            for parameter in tool.parameters:
                rows.append(
                    {
                        "server_id": server.server_id,
                        "server_name": server.name,
                        "child_link": server.child_link,
                        "tool_name": tool.name,
                        "tool_slug": tool.slug or "",
                        "tool_description": tool.description,
                        "parameter_name": parameter.name,
                        "parameter_required": _format_required(parameter.required),
                        "parameter_type": parameter.param_type or "",
                        "parameter_description": parameter.description,
                    }
                )
        else:
            rows.append(
                {
                    "server_id": server.server_id,
                    "server_name": server.name,
                    "child_link": server.child_link,
                    "tool_name": tool.name,
                    "tool_slug": tool.slug or "",
                    "tool_description": tool.description,
                    "parameter_name": "",
                    "parameter_required": "",
                    "parameter_type": "",
                    "parameter_description": "",
                }
            )

    return rows


def _format_required(required: Optional[bool]) -> str:
    if required is True:
        return "required"
    if required is False:
        return "optional"
    return ""


def write_output_csv(rows: Iterable[Dict[str, Optional[str]]], output_path: Path = OUTPUT_CSV_PATH) -> None:
    """Append flattened rows to CSV (writing header only when file is new/empty)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        logger.warning("No tool data collected; skipping CSV write.")
        return

    write_header = not output_path.exists() or output_path.stat().st_size == 0

    fieldnames = [
        "server_id",
        "server_name",
        "child_link",
        "tool_name",
        "tool_slug",
        "tool_description",
        "parameter_name",
        "parameter_required",
        "parameter_type",
        "parameter_description",
    ]

    with output_path.open("a", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    logger.info("Appended %s rows to %s", len(rows), output_path)


def main() -> None:
    servers = load_servers()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_rows: List[Dict[str, Optional[str]]] = []
    for server in servers:
        logger.info("Scraping tools for %s (%s)", server.name, server.child_link)
        tools = scrape_server_tools(session, server)
        all_rows.extend(flatten_records(server, tools))
        time.sleep(REQUEST_PAUSE_SECONDS)

    write_output_csv(all_rows)


if __name__ == "__main__":
    main()
