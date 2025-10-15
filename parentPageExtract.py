"""
Utilities for scraping verified MCP server metadata from Smithery.

This module fetches the first five listing pages, caches their HTML locally,
extracts each server's name, relative child link, and short description, and
stores the results in `Data/mcp_servers.csv`.
"""

from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

import requests
from bs4 import BeautifulSoup
from requests import Response, Session
from requests.exceptions import HTTPError, RequestException


BASE_URL = "https://smithery.ai"
SEARCH_PATH = "/search"
SEARCH_QUERY = "is:verified"
TOTAL_PAGES = 5  # base page + four additional pages
REQUEST_PAUSE_SECONDS = 1.0
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "Data"
OUTPUT_CSV = DATA_DIR / "mcp_servers.csv"
HTML_OUTPUT_DIR = DATA_DIR / "HTMLData"


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class MCPServer:
    """Container for MCP server metadata."""

    name: str
    child_link: str
    description: str


def fetch_search_pages(session: Session, total_pages: int) -> Iterator[str]:
    """
    Yield HTML content for each Smithery search page up to `total_pages`.

    Parameters
    ----------
    session : Session
        Shared HTTP session for efficient connection reuse.
    total_pages : int
        Number of search result pages to request (first page is page=1).
    """
    params = {"q": SEARCH_QUERY}
    HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for page_number in range(1, total_pages + 1):
        if page_number > 1:
            params["page"] = page_number
        else:
            params.pop("page", None)

        url = f"{BASE_URL}{SEARCH_PATH}"
        logger.info("Fetching page %s → %s", page_number, url)
        response = perform_request(session, url, params=params)
        html_text = response.text

        html_path = HTML_OUTPUT_DIR / f"smithery_verified_page_{page_number}.html"
        save_html_content(html_path, html_text)
        yield html_text

        if page_number != total_pages:
            time.sleep(REQUEST_PAUSE_SECONDS)


def perform_request(session: Session, url: str, *, params: dict | None = None) -> Response:
    """Perform an HTTP GET request with basic error handling."""
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response
    except HTTPError as exc:
        logger.error("HTTP error %s while fetching %s", exc.response.status_code, exc.response.url)
        raise
    except RequestException as exc:
        logger.error("Request error while fetching %s: %s", url, exc)
        raise


def parse_servers(html: str) -> List[MCPServer]:
    """Extract MCP server entries from a Smithery search page."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select(
        "a[role='listitem'][class*='hover:shadow-primary'][href^='/server/']"
    )
    servers: List[MCPServer] = []

    for anchor in anchors:
        name_tag = anchor.select_one("h3.text-base.font-semibold") or anchor.select_one("h3")
        description_tag = anchor.select_one(
            "p.text-muted-foreground.text-sm.leading-relaxed"
        ) or anchor.select_one("p")
        href = anchor.get("href")

        if not (name_tag and description_tag and href):
            # Skip incomplete entries.
            continue

        name = name_tag.get_text(strip=True)
        description = description_tag.get_text(" ", strip=True)
        child_link = href.strip()
        servers.append(MCPServer(name=name, child_link=child_link, description=description))

    return servers


def deduplicate_servers(servers: Iterable[MCPServer]) -> List[MCPServer]:
    """
    Remove duplicate entries (by child link) while preserving the first occurrence.
    """
    seen_links: set[str] = set()
    unique_servers: List[MCPServer] = []
    for server in servers:
        if server.child_link in seen_links:
            continue
        seen_links.add(server.child_link)
        unique_servers.append(server)
    return unique_servers


def save_html_content(output_path: Path, html: str) -> None:
    """Store raw HTML to disk for reference/debugging."""
    output_path.write_text(html, encoding="utf-8")


def write_to_csv(servers: Iterable[MCPServer], output_path: Path) -> None:
    """Persist MCP server metadata to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["name", "child_link", "description"])
        for server in servers:
            writer.writerow([server.name, server.child_link, server.description])


def scrape_mcp_servers(total_pages: int = TOTAL_PAGES) -> List[MCPServer]:
    """
    Orchestrate the scraping workflow and return collected entries.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    servers: List[MCPServer] = []
    for html in fetch_search_pages(session, total_pages):
        servers.extend(parse_servers(html))

    unique_servers = deduplicate_servers(servers)
    write_to_csv(unique_servers, OUTPUT_CSV)
    logger.info("Saved %s servers to %s", len(unique_servers), OUTPUT_CSV)
    return unique_servers


if __name__ == "__main__":
    scrape_mcp_servers()
