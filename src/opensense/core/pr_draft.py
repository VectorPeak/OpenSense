"""Local pull request draft generation from audited issue artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from opensense.config import workspace_path
from opensense.core.issue_ref import IssueRef
from opensense.core.sandbox import load_sandbox
from opensense.storage.packs import ensure_pack_can_write, pack_paths, require_valid_pack


@dataclass(frozen=True)
class PrDraftResult:
    issue_ref: str
    root: Path
    written_files: tuple[Path, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def draft_workspace(issue_ref: IssueRef, workspace: Path) -> Path:
    try:
        sandbox = load_sandbox(issue_ref, workspace)
    except FileNotFoundError:
        return workspace
    path = Path(sandbox.real_worktree_path).resolve()
    if not path.exists():
        raise FileNotFoundError("Sandbox worktree no longer exists. Recreate it or remove sandbox.json.")
    return path


def git_output(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False, timeout=30)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def format_command(command: object) -> str:
    parts = [str(part) for part in command] if isinstance(command, (list, tuple)) else [str(command)]
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def load_test_state(paths, issue_ref: IssueRef, cwd: Path) -> dict[str, Any]:
    if not paths.test_run_json.exists():
        return {
            "status": "not_run",
            "exit_code": None,
            "command": [],
            "duration_seconds": None,
            "message": "Tests have not been run yet.",
        }
    data = json.loads(paths.test_run_json.read_text(encoding="utf-8"))
    status = str(data.get("status") or "unknown")
    exit_code = data.get("exit_code")
    command = data.get("command") or []
    valid = (
        data.get("kind") == "opensense.test_run"
        and data.get("issue_ref") == issue_ref.ref
        and status in {"passed", "failed", "timeout"}
        and isinstance(command, list)
    )
    if status == "passed" and (exit_code != 0 or not command):
        valid = False
    current_commit = git_output(cwd, ["rev-parse", "HEAD"])
    current_dirty = git_output(cwd, ["status", "--porcelain"])
    stale = valid and status == "passed" and (
        str(data.get("git_commit") or "") != current_commit or str(data.get("dirty_status") or "") != current_dirty
    )
    if not valid:
        return {
            "status": "not_verified",
            "exit_code": None,
            "command": [],
            "duration_seconds": None,
            "message": "Stored test-run.json is invalid or inconsistent, so this draft does not treat it as verification.",
        }
    if stale:
        return {
            "status": "stale",
            "exit_code": exit_code,
            "command": command,
            "duration_seconds": data.get("duration_seconds"),
            "message": "Tests succeeded before the current local state changed; rerun tests before opening a PR.",
        }
    return {
        "status": status,
        "exit_code": exit_code,
        "command": command,
        "duration_seconds": data.get("duration_seconds"),
        "message": "",
    }


def test_section(test_state: dict[str, Any]) -> list[str]:
    status = test_state["status"]
    lines = [
        "## Tests",
        "",
        f"- Status: {status}",
        f"- Exit code: {test_state['exit_code']}",
    ]
    command = test_state.get("command") or []
    if command:
        lines.append(f"- Command: `{format_command(command)}`")
    if status == "not_run":
        lines.append("- Tests have not been run yet.")
    elif status in {"not_verified", "stale"}:
        lines.append(f"- {test_state['message']}")
    elif status != "passed":
        lines.append("- This result should be treated as not verified until the command succeeds.")
    return lines


def draft_markdown(pack: dict[str, Any], issue_ref: IssueRef, test_state: dict[str, Any], diffstat: str) -> str:
    issue = pack.get("issue", {})
    title = issue.get("title") or issue_ref.ref
    changes = ["- Patch not applied yet."] if not diffstat else [f"- Current local diff:\n\n```text\n{diffstat}\n```"]
    lines = [
        f"# {title}",
        "",
        f"Related to {issue_ref.ref}",
        "",
        "## Summary",
        "",
        "- This is a local draft generated from OpenSense evidence.",
        "- Keep the final PR narrow and tied to the linked issue.",
        "",
        "## Changes",
        "",
        *changes,
        "",
        *test_section(test_state),
        "",
        "## Risks / Not Verified",
        "",
        "- Review the final diff before opening a PR.",
        "- Do not claim maintainer intent or issue ownership without confirmation.",
        "",
        "## Safety",
        "",
        "- This command only wrote local draft files.",
        "- No commit, push, GitHub comment, or PR creation was performed.",
    ]
    return "\n".join(lines)


def generate_pr_draft(issue_ref: IssueRef, workspace: Path | None = None, *, force: bool = False) -> PrDraftResult:
    root = workspace_path(workspace)
    paths = pack_paths(issue_ref, root)
    payload = require_valid_pack(paths, issue_ref.ref)
    ensure_pack_can_write(paths, ("pr-draft.json", "pr-draft.md"), force=force)
    cwd = draft_workspace(issue_ref, root)
    diffstat = git_output(cwd, ["diff", "--stat"])
    test_state = load_test_state(paths, issue_ref, cwd)
    metadata: dict[str, object] = {
        "schema_version": 1,
        "kind": "opensense.pr_draft",
        "issue_ref": issue_ref.ref,
        "generated_at": utc_now(),
        "cwd": str(cwd),
        "test_status": test_state["status"],
        "test_exit_code": test_state["exit_code"],
        "has_local_diff": bool(diffstat),
        "git_commit_performed": False,
        "git_push_performed": False,
        "github_write_performed": False,
    }
    markdown = draft_markdown(payload["pack"], issue_ref, test_state, diffstat)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.pr_draft_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    paths.pr_draft_md.write_text(markdown.rstrip() + "\n", encoding="utf-8", newline="\n")
    return PrDraftResult(issue_ref=issue_ref.ref, root=paths.root, written_files=(paths.pr_draft_json, paths.pr_draft_md))
