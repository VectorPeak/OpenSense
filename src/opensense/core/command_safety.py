"""Shared command display and safety helpers."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess


BLOCKED_COMMAND_PATTERNS = (
    ("git", "push"),
    ("git", "commit"),
    ("gh", "pr", "create"),
    ("gh", "issue", "comment"),
    ("gh", "pr", "comment"),
    ("gh", "api"),
)

SHELL_WRAPPERS = {"cmd", "powershell", "pwsh", "sh", "bash", "zsh"}


def normalized_executable(value: str) -> str:
    name = Path(value).name.lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def normalized_command(command: tuple[str, ...]) -> tuple[str, ...]:
    if not command:
        return ()
    return (normalized_executable(command[0]), *(part.lower() for part in command[1:]))


def canonical_command(command: tuple[str, ...]) -> tuple[str, ...]:
    normalized = normalized_command(command)
    if not normalized or normalized[0] != "git":
        return normalized
    index = 1
    options_with_value = {"-c", "-C", "--git-dir", "--work-tree", "--namespace"}
    while index < len(normalized):
        part = normalized[index]
        if part == "--":
            index += 1
            break
        if part in options_with_value:
            index += 2
            continue
        if any(part.startswith(prefix + "=") for prefix in options_with_value):
            index += 1
            continue
        if part.startswith("-"):
            index += 1
            continue
        break
    return ("git", *normalized[index:])


def validate_no_obvious_remote_write(command: tuple[str, ...], *, label: str) -> None:
    if not command:
        raise ValueError(f"{label} command is required.")
    normalized = canonical_command(command)
    if normalized[0] in SHELL_WRAPPERS:
        raise ValueError("Refusing to run shell wrapper commands for agent-controlled execution.")
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if normalized[: len(pattern)] == pattern:
            raise ValueError("Refusing to run commands that commit, push, open PRs, or comment on GitHub.")


def format_command(command: object) -> str:
    parts = [str(part) for part in command] if isinstance(command, (list, tuple)) else [str(command)]
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)
