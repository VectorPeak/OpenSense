"""Agent handoff and controlled sandbox apply workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import subprocess
import time
from pathlib import Path

from opensense.config import workspace_path
from opensense.core.command_safety import validate_no_obvious_remote_write
from opensense.core.issue_ref import IssueRef
from opensense.core.sandbox import SandboxInfo, load_sandbox, sandbox_root
from opensense.core.test_capture import redact_text
from opensense.storage.packs import ensure_pack_can_write, pack_paths, require_valid_pack


@dataclass(frozen=True)
class AgentArtifactResult:
    issue_ref: str
    root: Path
    status: str
    exit_code: int | None
    written_files: tuple[Path, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_output(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False, timeout=30)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def validate_agent_command(command: tuple[str, ...]) -> None:
    validate_no_obvious_remote_write(command, label="Agent")


def require_patch_proposal(paths) -> None:
    if not paths.patch_proposal_md.exists():
        raise FileNotFoundError("Patch proposal not found. Run `opensense propose <issue-url>` before agent apply.")


def require_sandbox_worktree(issue_ref: IssueRef, workspace: Path) -> tuple[SandboxInfo, Path]:
    sandbox = load_sandbox(issue_ref, workspace)
    worktree = Path(sandbox.real_worktree_path).resolve()
    if not worktree.exists():
        raise FileNotFoundError("Sandbox worktree no longer exists. Recreate it or remove sandbox.json.")
    try:
        worktree.relative_to(sandbox_root(issue_ref, workspace).resolve())
    except ValueError as exc:
        raise ValueError("Sandbox worktree must stay inside the OpenSense sandbox root.") from exc
    return sandbox, worktree


def status_porcelain_z(cwd: Path) -> str:
    result = subprocess.run(["git", "status", "--porcelain=v1", "-z"], cwd=cwd, check=False, capture_output=True, timeout=30)
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def modified_paths(cwd: Path) -> list[str]:
    raw = status_porcelain_z(cwd)
    if not raw:
        return []
    entries = [entry for entry in raw.split("\0") if entry]
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        status = entry[:2]
        path = entry[3:] if len(entry) > 3 else ""
        if ("R" in status or "C" in status) and index + 1 < len(entries):
            paths.append(path)
            index += 2
            continue
        if path:
            paths.append(path)
        index += 1
    return [path for path in paths if not path.startswith(".opensense/")]


def append_untracked_summary(diffstat: str, paths: list[str]) -> str:
    untracked = [path for path in paths if path and not diffstat.count(path)]
    if not untracked:
        return diffstat
    lines = [diffstat.rstrip(), "Untracked files:", *(f"  {path}" for path in untracked)]
    return "\n".join(line for line in lines if line) + "\n"


def handoff_markdown(pack: dict, issue_ref: IssueRef, sandbox: SandboxInfo, paths) -> str:
    issue = pack.get("issue", {})
    commands = pack.get("test_guidance", {}).get("suggested_commands", [])
    constraints = pack.get("agent_constraints", [])
    return "\n".join(
        [
            "# Agent Handoff",
            "",
            f"Issue: {issue_ref.ref}",
            f"Title: {issue.get('title', 'unknown')}",
            f"Sandbox worktree: `{sandbox.real_worktree_path}`",
            f"Patch proposal: `{paths.patch_proposal_md.name}`",
            "",
            "## Goal",
            "",
            "- Make the narrowest useful change for this issue.",
            "- Prefer a focused bug fix or regression test over broad refactors.",
            "",
            "## Files To Read First",
            "",
            "- `issue.md`",
            "- `repo.md`",
            "- `patch-proposal.md`",
            "",
            "## Suggested Tests",
            *(f"- `{command}`" for command in commands),
            *(["- Read repository test instructions and choose the smallest relevant test."] if not commands else []),
            "",
            "## Hard Boundaries",
            "",
            "- Do not commit, push, open a PR, or comment on GitHub.",
            "- Stop if the work touches auth, security, privacy, payment, license, legal, or CI permissions.",
            "- Stop if the diff grows beyond five files or roughly 300 changed lines.",
            *(f"- {constraint}" for constraint in constraints),
        ]
    )


def generate_agent_handoff(issue_ref: IssueRef, workspace: Path | None = None, *, force: bool = False) -> AgentArtifactResult:
    root = workspace_path(workspace)
    paths = pack_paths(issue_ref, root)
    payload = require_valid_pack(paths, issue_ref.ref)
    require_patch_proposal(paths)
    sandbox, _ = require_sandbox_worktree(issue_ref, root)
    ensure_pack_can_write(paths, ("agent-handoff.json", "agent-handoff.md"), force=force)
    metadata: dict[str, object] = {
        "schema_version": 1,
        "kind": "opensense.agent_handoff",
        "issue_ref": issue_ref.ref,
        "generated_at": utc_now(),
        "sandbox_id": sandbox.sandbox_id,
        "worktree_path": sandbox.real_worktree_path,
        "patch_proposal": paths.patch_proposal_md.name,
        "source_modified": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "github_write_performed": False,
    }
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.agent_handoff_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    paths.agent_handoff_md.write_text(handoff_markdown(payload["pack"], issue_ref, sandbox, paths).rstrip() + "\n", encoding="utf-8", newline="\n")
    return AgentArtifactResult(issue_ref=issue_ref.ref, root=paths.root, status="written", exit_code=0, written_files=(paths.agent_handoff_json, paths.agent_handoff_md))


def generate_agent_apply(
    issue_ref: IssueRef,
    command: tuple[str, ...],
    workspace: Path | None = None,
    *,
    force: bool = False,
    timeout: int = 1800,
) -> AgentArtifactResult:
    validate_agent_command(command)
    root = workspace_path(workspace)
    paths = pack_paths(issue_ref, root)
    require_valid_pack(paths, issue_ref.ref)
    require_patch_proposal(paths)
    sandbox, worktree = require_sandbox_worktree(issue_ref, root)
    ensure_pack_can_write(paths, ("agent-apply.json", "agent-output.log", "diff.patch", "diffstat.txt"), force=force)
    before_commit = git_output(worktree, ["rev-parse", "HEAD"])
    started_at = utc_now()
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=worktree, text=True, capture_output=True, check=False, timeout=timeout)
        exit_code: int | None = result.returncode
        raw_output = (result.stdout or "") + (result.stderr or "")
        output = redact_text(raw_output)
        status = "passed" if exit_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        raw_output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        output = redact_text(raw_output)
        status = "timeout"
    finished_at = utc_now()
    modified_files = modified_paths(worktree)
    diff_patch = redact_text(git_output(worktree, ["diff", "HEAD", "--binary"]))
    diffstat = append_untracked_summary(git_output(worktree, ["diff", "HEAD", "--stat"]), modified_files)
    dirty_status = git_output(worktree, ["status", "--porcelain"])
    after_commit = git_output(worktree, ["rev-parse", "HEAD"])
    commit_performed = bool(before_commit and after_commit and before_commit != after_commit)
    metadata: dict[str, object] = {
        "schema_version": 1,
        "kind": "opensense.agent_apply",
        "issue_ref": issue_ref.ref,
        "sandbox_id": sandbox.sandbox_id,
        "cwd": str(worktree),
        "command": list(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(time.monotonic() - started, 3),
        "exit_code": exit_code,
        "status": status,
        "output_log": "agent-output.log",
        "diff_patch": "diff.patch",
        "diffstat": "diffstat.txt",
        "modified_files": modified_files,
        "base_commit": before_commit,
        "git_commit": after_commit,
        "dirty_status": dirty_status,
        "source_modified": bool(dirty_status),
        "redaction_applied": output != raw_output,
        "git_commit_performed": commit_performed,
        "git_push_performed": "not_asserted",
        "github_write_performed": "not_asserted",
    }
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.agent_output_log.write_text(output, encoding="utf-8", newline="\n")
    paths.diff_patch.write_text(diff_patch, encoding="utf-8", newline="\n")
    paths.diffstat_txt.write_text(diffstat, encoding="utf-8", newline="\n")
    paths.agent_apply_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return AgentArtifactResult(
        issue_ref=issue_ref.ref,
        root=paths.root,
        status=status,
        exit_code=exit_code,
        written_files=(paths.agent_apply_json, paths.agent_output_log, paths.diff_patch, paths.diffstat_txt),
    )
