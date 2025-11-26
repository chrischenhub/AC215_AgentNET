#!/usr/bin/env python3
"""
Generate a formatted TXT summary of DVC-tracked data versions.

By default this script inspects the git history of ``src/models/data_mcpinfo.dvc``
and writes ``docs/data_version_summary.txt`` in the repository.

Example:
    python summarize_data_versions.py
    python summarize_data_versions.py --dvc-file src/models/data_mcpinfo.dvc --output out.txt
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def run_cmd(args: List[str], cwd: Path) -> str:
    """Run a command and return stdout, raising a helpful error on failure."""
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({' '.join(args)}): {result.stderr.strip() or result.stdout}"
        )
    return result.stdout


def try_parse_yaml(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse outs from a DVC file using PyYAML if available.

    The repo does not depend on PyYAML, so this is best-effort only.
    """
    try:
        import yaml  # type: ignore
    except Exception:
        return None

    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return None

    outs = data.get("outs", [])
    return outs if isinstance(outs, list) else None


def manual_parse_outs(text: str) -> List[Dict[str, Any]]:
    """
    Minimal, dependency-free parser for the simple DVC YAML structure.

    It understands the common ``outs:`` list with ``key: value`` pairs and
    ignores anything it does not recognise.
    """
    outs: List[Dict[str, Any]] = []
    in_outs = False
    current: Optional[Dict[str, Any]] = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if not in_outs:
            if stripped.startswith("outs"):
                in_outs = True
            continue

        if stripped.startswith("-"):
            if current:
                outs.append(current)
            current = {}
            after_dash = stripped[1:].strip()
            if after_dash and ":" in after_dash:
                key, value = after_dash.split(":", 1)
                current[key.strip()] = value.strip()
            continue

        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()

    if current:
        outs.append(current)

    return outs


def parse_outs(text: str) -> List[Dict[str, Any]]:
    """Return outs from a DVC file using YAML if available, else a manual parser."""
    from_yaml = try_parse_yaml(text)
    if from_yaml is not None:
        return from_yaml
    return manual_parse_outs(text)


def coerce_int(value: Any) -> Optional[int]:
    """Convert common numeric-like strings to int, otherwise None."""
    try:
        return int(str(value).strip())
    except Exception:
        return None


def format_bytes(size: Optional[int]) -> str:
    """Human-readable byte formatting."""
    if size is None:
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    remaining = float(size)
    for unit in units:
        if abs(remaining) < 1024 or unit == units[-1]:
            return f"{remaining:.2f} {unit}"
        remaining /= 1024.0
    return f"{size} B"


def repo_root(start: Path) -> Path:
    """Return git repo root if available, else the starting directory."""
    try:
        root = run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=start).strip()
        return Path(root)
    except Exception:
        return start


def collect_versions(dvc_file: Path, root: Path) -> List[Dict[str, Any]]:
    """
    Walk git history for the DVC file and collect version metadata.

    Each entry contains commit hash, commit date, and parsed outs.
    """
    log_output = run_cmd(
        ["git", "log", "--format=%H|%ad", "--date=iso-strict", "--", str(dvc_file)],
        cwd=root,
    ).strip()

    versions: List[Dict[str, Any]] = []
    if not log_output:
        return versions

    for line in log_output.splitlines():
        if "|" not in line:
            continue
        commit_hash, commit_date = line.split("|", 1)
        raw_file = run_cmd(
            ["git", "show", f"{commit_hash}:{dvc_file.as_posix()}"],
            cwd=root,
        )
        outs = parse_outs(raw_file)
        versions.append(
            {
                "commit": commit_hash,
                "date": commit_date,
                "outs": outs,
            }
        )

    return versions


def write_summary(
    output: Path,
    dvc_file: Path,
    versions: Iterable[Dict[str, Any]],
) -> None:
    """Render a plain-text summary to ``output``."""
    now = datetime.now().isoformat(timespec="seconds")
    versions_list = list(versions)

    unique_hashes = {
        o.get("md5") or o.get("etag") or ""
        for version in versions_list
        for o in version.get("outs", [])
    }
    unique_hashes.discard("")

    lines: List[str] = []
    lines.append(f"Data Version Summary for {dvc_file.as_posix()}")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append(f"Versions found: {len(versions_list)}")
    lines.append(f"Unique data hashes: {len(unique_hashes)}")
    lines.append("")
    lines.append("Versions (newest first):")

    for idx, version in enumerate(versions_list, start=1):
        commit = version.get("commit", "")[:7]
        date = version.get("date", "")
        outs = version.get("outs", []) or []
        if not outs:
            lines.append(f"{idx}) {commit} @ {date} - no outs parsed")
            continue

        for out in outs:
            md5 = out.get("md5") or "unknown"
            algo = out.get("hash") or "md5"
            nfiles = coerce_int(out.get("nfiles"))
            size = coerce_int(out.get("size"))
            path = out.get("path") or "unknown"

            lines.append(f"{idx}) commit {commit} @ {date}")
            lines.append(f"    path: {path}")
            lines.append(f"    data hash: {md5} ({algo})")
            lines.append(
                f"    files: {nfiles if nfiles is not None else 'unknown'} | size: {format_bytes(size)}"
            )
            lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Produce a formatted TXT summary of DVC-tracked data versions."
    )
    parser.add_argument(
        "--dvc-file",
        default="src/models/data_mcpinfo.dvc",
        help="Path to the .dvc file to inspect (relative to repo root).",
    )
    parser.add_argument(
        "--output",
        default="docs/data_version_summary.txt",
        help="Where to write the summary TXT file.",
    )
    args = parser.parse_args()

    start = Path.cwd()
    root = repo_root(start)
    dvc_path = (root / args.dvc_file).resolve()
    if not dvc_path.exists():
        raise SystemExit(f"DVC file not found: {dvc_path}")

    versions = collect_versions(dvc_path.relative_to(root), root)
    if not versions:
        raise SystemExit("No versions found in git history for the specified DVC file.")

    output_path = (root / args.output).resolve()
    write_summary(output_path, dvc_path.relative_to(root), versions)
    print(f"Wrote summary to {output_path}")


if __name__ == "__main__":
    main()
