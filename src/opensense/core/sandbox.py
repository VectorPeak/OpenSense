"""Isolated git worktree sandbox support."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from opensense.config import state_dir, workspace_path
from opensense.core.issue_ref import IssueRef
from opensense.storage.packs import pack_paths, require_valid_pack


@dataclass(frozen=True)
class SandboxInfo:
    issue_ref: str
    sandbox_id: str
    branch_name: str
    worktree_path: str
    real_worktree_path: str
    base_commit: str | None
    created_at: str
    safety_status: str
    dirty_policy: str
    dirty_snapshot: str
    pack_manifest_hash: str
    operations_allowed: tuple[str, ...]
    operations_denied: tuple[str, ...]
    source_modified: bool
    github_write_performed: bool


def branch_slug(issue_ref: IssueRef) -> str:
    repo = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{issue_ref.owner}-{issue_ref.repo}").strip("-").lower()
    return f"opensense/sandbox/{repo}-{issue_ref.number}"[:120]


def sandbox_id(issue_ref: IssueRef) -> str:
    repo = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{issue_ref.owner}-{issue_ref.repo}").strip("-").lower()
    return f"{repo}-{issue_ref.number}"[:80]


def sandbox_root(issue_ref: IssueRef, workspace: Path | None = None) -> Path:
    return state_dir(workspace) / "sandboxes" / sandbox_id(issue_ref)


def default_worktree_path(issue_ref: IssueRef, workspace: Path | None = None) -> Path:
    return sandbox_root(issue_ref, workspace) / "worktree"


def run_git(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=workspace, check=False, capture_output=True, text=True, timeout=30)


def git_output(workspace: Path, args: list[str]) -> str | None:
    result = run_git(workspace, args)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def dirty_worktree(workspace: Path) -> bool:
    status = git_output(workspace, ["status", "--porcelain"])
    return bool(status)


def dirty_snapshot(workspace: Path) -> str:
    return git_output(workspace, ["status", "--porcelain"]) or ""


def git_state_in_progress(workspace: Path) -> str | None:
    top_level = git_output(workspace, ["rev-parse", "--show-toplevel"])
    if not top_level or Path(top_level).resolve() != workspace.resolve():
        return "git metadata unavailable"
    git_dir_text = git_output(workspace, ["rev-parse", "--git-dir"])
    if not git_dir_text:
        return "git metadata unavailable"
    git_dir = (workspace / git_dir_text).resolve()
    markers = {
        "MERGE_HEAD": "merge in progress",
        "CHERRY_PICK_HEAD": "cherry-pick in progress",
        "REVERT_HEAD": "revert in progress",
        "rebase-merge": "rebase in progress",
        "rebase-apply": "rebase in progress",
    }
    for marker, message in markers.items():
        if (git_dir / marker).exists():
            return message
    return None


def ensure_inside(child: Path, parent: Path) -> None:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError as exc:
        raise ValueError("Sandbox path must stay inside the OpenSense sandbox root.") from exc


def branch_exists(workspace: Path, branch: str) -> bool:
    return run_git(workspace, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode == 0


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def create_sandbox(
    issue_ref: IssueRef,
    workspace: Path | None = None,
    *,
    allow_dirty: bool = False,
    worktree_path: Path | None = None,
) -> SandboxInfo:
    root = workspace_path(workspace)
    paths = pack_paths(issue_ref, root)
    require_valid_pack(paths, issue_ref.ref)
    state = git_state_in_progress(root)
    if state:
        raise ValueError(f"Cannot create sandbox while {state}.")
    snapshot = dirty_snapshot(root)
    if snapshot and not allow_dirty:
        raise ValueError("Workspace has uncommitted changes. Re-run with --allow-dirty only if you accept that risk.")
    controlled_root = sandbox_root(issue_ref, root).resolve()
    target = (worktree_path or default_worktree_path(issue_ref, root)).resolve()
    ensure_inside(target, controlled_root)
    if target.exists():
        raise FileExistsError(f"Sandbox worktree already exists: {target}")
    branch = branch_slug(issue_ref)
    if branch_exists(root, branch):
        raise FileExistsError(f"Sandbox branch already exists: {branch}")
    base_commit = git_output(root, ["rev-parse", "HEAD"])
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(root, ["worktree", "add", "-b", branch, str(target), "HEAD"])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git worktree add failed").strip()
        raise RuntimeError(detail)
    ensure_inside(target, controlled_root)
    info = SandboxInfo(
        issue_ref=issue_ref.ref,
        sandbox_id=sandbox_id(issue_ref),
        branch_name=branch,
        worktree_path=str(target),
        real_worktree_path=str(target.resolve()),
        base_commit=base_commit,
        created_at=datetime.now(timezone.utc).isoformat(),
        safety_status="created",
        dirty_policy="allowed" if allow_dirty else "clean_required",
        dirty_snapshot=snapshot,
        pack_manifest_hash=file_sha256(paths.manifest_json),
        operations_allowed=("git worktree add", "metadata write"),
        operations_denied=("source write", "git commit", "git push", "github pr", "github comment"),
        source_modified=False,
        github_write_performed=False,
    )
    paths.sandbox_json.write_text(json.dumps(asdict(info), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return info


def load_sandbox(issue_ref: IssueRef, workspace: Path | None = None) -> SandboxInfo:
    paths = pack_paths(issue_ref, workspace)
    if not paths.sandbox_json.exists():
        raise FileNotFoundError("Sandbox not found. Run `opensense sandbox create <issue-url>` first.")
    data = json.loads(paths.sandbox_json.read_text(encoding="utf-8"))
    return SandboxInfo(**data)
