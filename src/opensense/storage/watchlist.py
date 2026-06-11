"""Watchlist persistence for repositories and user skills."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from opensense.config import watchlist_path


REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SKILL_RE = re.compile(r"^[A-Za-z0-9_.+#-]+$")


@dataclass(frozen=True)
class Watchlist:
    repositories: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


def validate_repo_name(name: str) -> str:
    candidate = name.strip()
    if not REPO_RE.match(candidate):
        raise ValueError("Repository must use owner/repo format.")
    return candidate


def validate_skill_name(name: str) -> str:
    candidate = name.strip().lower()
    if not SKILL_RE.match(candidate):
        raise ValueError("Skill must be a single tag such as python, cli, llm, tests, or github-actions.")
    return candidate


def ensure_watchlist_exists(workspace: Path | None = None) -> Path:
    path = watchlist_path(workspace)
    if not path.exists():
        raise FileNotFoundError("OpenSense is not initialized. Run `opensense init` first.")
    return path


def load_watchlist_data(workspace: Path | None = None) -> Watchlist:
    path = ensure_watchlist_exists(workspace)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    repositories = data.get("repositories", [])
    skills = data.get("skills", [])
    return Watchlist(
        repositories=tuple(str(item["name"]) for item in repositories if isinstance(item, dict) and item.get("name")),
        skills=tuple(str(item) for item in skills if item),
    )


def load_repositories(workspace: Path | None = None) -> list[str]:
    return list(load_watchlist_data(workspace).repositories)


def load_skills(workspace: Path | None = None) -> list[str]:
    return list(load_watchlist_data(workspace).skills)


def render_watchlist(watchlist: Watchlist) -> str:
    lines: list[str] = []
    if watchlist.skills:
        quoted = ", ".join(f'"{skill}"' for skill in watchlist.skills)
        lines.append(f"skills = [{quoted}]")
    else:
        lines.append("skills = []")

    if not watchlist.repositories:
        lines.append("repositories = []")
    else:
        lines.append("")
        for repo in watchlist.repositories:
            lines.extend(["[[repositories]]", f'name = "{repo}"', ""])

    return "\n".join(lines).rstrip() + "\n"


def save_watchlist(watchlist: Watchlist, workspace: Path | None = None) -> None:
    path = ensure_watchlist_exists(workspace)
    path.write_text(render_watchlist(watchlist), encoding="utf-8", newline="\n")


def add_repository(name: str, workspace: Path | None = None) -> bool:
    repo = validate_repo_name(name)
    watchlist = load_watchlist_data(workspace)
    if repo in watchlist.repositories:
        return False
    save_watchlist(
        Watchlist(repositories=(*watchlist.repositories, repo), skills=watchlist.skills),
        workspace,
    )
    return True


def add_skill(name: str, workspace: Path | None = None) -> bool:
    skill = validate_skill_name(name)
    watchlist = load_watchlist_data(workspace)
    if skill in watchlist.skills:
        return False
    save_watchlist(
        Watchlist(repositories=watchlist.repositories, skills=(*watchlist.skills, skill)),
        workspace,
    )
    return True
