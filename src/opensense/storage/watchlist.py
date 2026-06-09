"""Watchlist persistence."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from opensense.config import watchlist_path


REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def validate_repo_name(name: str) -> str:
    candidate = name.strip()
    if not REPO_RE.match(candidate):
        raise ValueError("Repository must use owner/repo format.")
    return candidate


def ensure_watchlist_exists(workspace: Path | None = None) -> Path:
    path = watchlist_path(workspace)
    if not path.exists():
        raise FileNotFoundError("OpenSense is not initialized. Run `opensense init` first.")
    return path


def load_watchlist(workspace: Path | None = None) -> list[str]:
    path = ensure_watchlist_exists(workspace)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    repositories = data.get("repositories", [])
    return [str(item["name"]) for item in repositories if isinstance(item, dict) and item.get("name")]


def render_watchlist(repositories: list[str]) -> str:
    if not repositories:
        return "repositories = []\n"
    lines: list[str] = []
    for repo in repositories:
        lines.extend(["[[repositories]]", f'name = "{repo}"', ""])
    return "\n".join(lines).rstrip() + "\n"


def save_watchlist(repositories: list[str], workspace: Path | None = None) -> None:
    path = ensure_watchlist_exists(workspace)
    path.write_text(render_watchlist(repositories), encoding="utf-8", newline="\n")


def add_repository(name: str, workspace: Path | None = None) -> bool:
    repo = validate_repo_name(name)
    repositories = load_watchlist(workspace)
    if repo in repositories:
        return False
    repositories.append(repo)
    save_watchlist(repositories, workspace)
    return True
