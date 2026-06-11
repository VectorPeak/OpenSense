"""Storage helpers for OpenSense context packs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opensense.config import state_dir
from opensense.core.issue_ref import IssueRef


@dataclass(frozen=True)
class PackPaths:
    root: Path
    issue_md: Path
    repo_md: Path
    files_md: Path
    tests_md: Path
    plan_md: Path
    risks_md: Path
    agent_md: Path
    pr_summary_md: Path
    test_evidence_md: Path
    maintainer_note_md: Path


PACK_FILENAMES = (
    "issue.md",
    "repo.md",
    "files.md",
    "tests.md",
    "plan.md",
    "risks.md",
    "agent.md",
)

EVIDENCE_FILENAMES = (
    "pr-summary.md",
    "test-evidence.md",
    "maintainer-note.md",
)


def pack_paths(issue_ref: IssueRef, workspace: Path | None = None) -> PackPaths:
    root = state_dir(workspace) / "packs" / issue_ref.slug
    return PackPaths(
        root=root,
        issue_md=root / "issue.md",
        repo_md=root / "repo.md",
        files_md=root / "files.md",
        tests_md=root / "tests.md",
        plan_md=root / "plan.md",
        risks_md=root / "risks.md",
        agent_md=root / "agent.md",
        pr_summary_md=root / "pr-summary.md",
        test_evidence_md=root / "test-evidence.md",
        maintainer_note_md=root / "maintainer-note.md",
    )


def ensure_pack_can_write(paths: PackPaths, filenames: tuple[str, ...], *, force: bool = False) -> None:
    if force:
        return
    existing = [name for name in filenames if (paths.root / name).exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Pack files already exist: {joined}. Re-run with --force to overwrite.")


def write_markdown_files(paths: PackPaths, files: dict[str, str], *, force: bool = False) -> tuple[Path, ...]:
    ensure_pack_can_write(paths, tuple(files), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in files.items():
        target = paths.root / name
        target.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
        written.append(target)
    return tuple(written)


def require_existing_pack(paths: PackPaths) -> None:
    missing = [name for name in PACK_FILENAMES if not (paths.root / name).exists()]
    if missing:
        raise FileNotFoundError("Context pack not found. Run `opensense pack <issue-url>` first.")
