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
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import HTTPError, RequestException


BASE_URL = "https://smithery.ai"
SERVERS_CSV_PATH = Path("Data/mcp_servers.csv")
OUTPUT_CSV_PATH = Path("Data/mcp_server_tools.csv")
HTML_CACHE_DIR = Path("Data/HTMLData/server_details")
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

    cache_html(server, 1, html)
    tool_dicts = extract_tool_dicts(html)
    if not tool_dicts:
        logger.info("No server payload found for %s", server.child_link)
        return []

    description_lookup = build_description_lookup(html)
    tools: List[Tool] = []
    for tool_data in tool_dicts:
        raw_title = (
            tool_data.get("title")
            or tool_data.get("annotations", {}).get("title")
            or tool_data.get("name")
            or ""
        )
        display_name, slug = split_tool_label(raw_title)
        slug = slug or tool_data.get("name")
        description_token = tool_data.get("description") or ""
        description = resolve_description(
            description_token, description_lookup, slug, display_name
        )
        parameters = extract_parameters_from_schema(tool_data.get("inputSchema") or {})
        tools.append(Tool(name=display_name, slug=slug, description=description, parameters=parameters))

    return tools


def fetch_server_page(session: Session, child_link: str, *, page: int) -> Optional[str]:
    """Fetch a server detail page, handling pagination via query params."""
    full_url = urljoin(BASE_URL, child_link)
    if page > 1:
        separator = "&" if "?" in full_url else "?"
        full_url = f"{full_url}{separator}{urlencode({'page': page})}"

    try:
        response = session.get(full_url, timeout=30)
        response.raise_for_status()
        return response.text
    except HTTPError as exc:
        logger.error("HTTP error %s while fetching %s", exc.response.status_code, exc.response.url)
    except RequestException as exc:
        logger.error("Request error while fetching %s: %s", full_url, exc)
    return None


def cache_html(server: ServerRecord, page: int, html: str) -> None:
    """Persist raw HTML for inspection."""
    slug = server.child_link.strip("/").replace("/", "_") or server.server_id
    HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{slug}_page{page}.html"
    (HTML_CACHE_DIR / filename).write_text(html, encoding="utf-8")


def extract_tool_dicts(html: str) -> List[Dict]:
    """Extract the list of tool dictionaries from the embedded scripts."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = [script for script in soup.find_all("script") if script.string]

    for script in scripts:
        decoded = bytes(script.string, "utf-8").decode("unicode_escape")
        idx = decoded.find('"tools":')
        if idx == -1:
            continue
        array_str = extract_json_array(decoded, idx + len('"tools":'))
        if not array_str:
            continue
        try:
            return json.loads(array_str)
        except json.JSONDecodeError:
            logger.debug("Failed to decode tools array")
            continue

    return []


def extract_json_array(buffer: str, start_idx: int) -> Optional[str]:
    """Extract a JSON array substring starting near `start_idx`."""
    length = len(buffer)
    while start_idx < length and buffer[start_idx] not in "[[":
        start_idx += 1

    if start_idx >= length or buffer[start_idx] != "[":
        return None

    bracket_depth = 0
    in_string = False
    escape = False
    for position in range(start_idx, length):
        char = buffer[position]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
            if bracket_depth == 0:
                return buffer[start_idx : position + 1]
    return None


def build_description_lookup(html: str) -> Dict[str, str]:
    """Build a lookup from RSC description tokens to plain text snippets."""
    lookup: Dict[str, str] = {}
    soup = BeautifulSoup(html, "html.parser")
    for div in soup.find_all("div", class_=lambda c: c and "border" in c.split()):
        header = div.find("h3")
        if not header:
            continue
        raw_label = normalize_text(header.get_text(" ", strip=True))
        display_name, slug = split_tool_label(raw_label)
        description = ""
        desc_block = div.find("div", class_=lambda c: c and "text-[14px]" in c)
        if desc_block:
            first_paragraph = desc_block.find("p")
            if first_paragraph:
                description = normalize_text(first_paragraph.get_text(" ", strip=True))
            else:
                description = normalize_text(desc_block.get_text(" ", strip=True))
        key = slug or display_name
        if key and description:
            lookup[key] = description
    return lookup


def resolve_description(
    description_field: str,
    description_lookup: Dict[str, str],
    slug: Optional[str],
    fallback_name: str,
) -> str:
    """Resolve tool description, accounting for RSC token indirection."""
    if not description_field:
        return ""
    if not description_field.startswith("$"):
        return normalize_text(description_field)

    if slug and slug in description_lookup:
        return description_lookup[slug]

    if fallback_name and fallback_name in description_lookup:
        return description_lookup[fallback_name]

    # Attempt secondary lookup by token (rarely available).
    token = description_field.lstrip("$")
    return description_lookup.get(token, fallback_name)


def extract_parameters_from_schema(schema: Dict) -> List[ToolParameter]:
    """Extract parameters from a JSON schema definition."""
    properties = schema.get("properties") or {}
    required_params = set(schema.get("required") or [])

    parameters: List[ToolParameter] = []
    for name, definition in properties.items():
        description = normalize_text(str(definition.get("description") or ""))
        param_type = ""
        if "type" in definition:
            if isinstance(definition["type"], list):
                param_type = ",".join(str(t) for t in definition["type"])
            else:
                param_type = str(definition["type"])
        parameter = ToolParameter(
            name=name,
            description=description,
            param_type=param_type or None,
            required=name in required_params,
        )
        parameters.append(parameter)

    return parameters


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
    """Write flattened rows to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        logger.warning("No tool data collected; skipping CSV write.")
        return

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

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Saved %s rows to %s", len(rows), output_path)


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
