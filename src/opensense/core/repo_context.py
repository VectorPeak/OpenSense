"""Lightweight local repository context scanning."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from opensense.config import workspace_path


DOC_FILES = (
    "README.md",
    "README_CN.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "package.json",
    "uv.lock",
    "requirements.txt",
    "pytest.ini",
)
DIRECTORIES = (
    "src",
    "tests",
    ".github/workflows",
    ".github/ISSUE_TEMPLATE",
    ".github/PULL_REQUEST_TEMPLATE",
    "docs",
)
SECRET_LIKE_NAMES = (".env", ".env.local", ".npmrc", ".pypirc", "id_rsa")
SECRET_SUFFIXES = (".pem", ".key")


@dataclass(frozen=True)
class RepoContext:
    workspace: str
    source_commit: str | None
    dirty_worktree: bool | None
    present_files: tuple[str, ...]
    present_directories: tuple[str, ...]
    test_hints: tuple[str, ...]
    safety_warnings: tuple[str, ...]
    skipped_sensitive_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def relative_if_present(root: Path, relative: str) -> str | None:
    target = root / relative
    try:
        resolved = target.resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    if target.exists():
        return relative
    return None


def git_value(root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def git_dirty(root: Path) -> bool | None:
    status = git_value(root, ["status", "--porcelain"])
    if status is None:
        return None
    return bool(status)


def infer_test_hints(present_files: tuple[str, ...], present_directories: tuple[str, ...]) -> tuple[str, ...]:
    hints: list[str] = []
    if "pyproject.toml" in present_files or "pytest.ini" in present_files or "tests" in present_directories:
        hints.append("uv run pytest")
        hints.append("pytest")
    if "package.json" in present_files:
        hints.append("npm test")
    if ".github/workflows" in present_directories:
        hints.append("Check matching GitHub Actions workflow before PR.")
    return tuple(dict.fromkeys(hints))


def scan_repo_context(workspace: Path | None = None) -> RepoContext:
    root = workspace_path(workspace)
    present_files = tuple(item for item in (relative_if_present(root, name) for name in DOC_FILES) if item)
    present_directories = tuple(item for item in (relative_if_present(root, name) for name in DIRECTORIES) if item)
    skipped_items = [".opensense/"]
    skipped_items.extend(name for name in SECRET_LIKE_NAMES if (root / name).exists())
    for directory in (".git",):
        if (root / directory).exists():
            skipped_items.append(f"{directory}/")
    skipped = tuple(skipped_items) + tuple(
        str(path.relative_to(root))
        for suffix in SECRET_SUFFIXES
        for path in root.glob(f"*{suffix}")
        if path.is_file() and path.parent == root
    )
    warnings: list[str] = []
    if skipped:
        warnings.append("Sensitive-looking local files were detected and intentionally not read.")
    commit = git_value(root, ["rev-parse", "HEAD"])
    dirty = git_dirty(root)
    if dirty:
        warnings.append("Workspace has uncommitted changes; keep pack evidence separate from user edits.")
    return RepoContext(
        workspace=".",
        source_commit=commit,
        dirty_worktree=dirty,
        present_files=present_files,
        present_directories=present_directories,
        test_hints=infer_test_hints(present_files, present_directories),
        safety_warnings=tuple(warnings),
        skipped_sensitive_paths=skipped,
    )
