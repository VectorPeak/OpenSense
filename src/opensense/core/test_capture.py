"""Capture real local test command evidence for one issue attempt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import subprocess
import time
from pathlib import Path

from opensense.config import workspace_path
from opensense.core.command_safety import format_command, validate_no_obvious_remote_write
from opensense.core.issue_ref import IssueRef
from opensense.core.sandbox import load_sandbox
from opensense.storage.packs import ensure_pack_can_write, pack_paths, require_valid_pack


REDACTION_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----.*?-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----", re.DOTALL),
)


@dataclass(frozen=True)
class TestRunResult:
    issue_ref: str
    root: Path
    status: str
    exit_code: int | None
    written_files: tuple[Path, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(value: str) -> str:
    redacted = value
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def validate_command(command: tuple[str, ...]) -> None:
    validate_no_obvious_remote_write(command, label="Test")


def command_cwd(issue_ref: IssueRef, workspace: Path) -> Path:
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


def build_evidence(metadata: dict[str, object]) -> str:
    status = metadata["status"]
    lines = [
        "# Test Evidence",
        "",
        "## Command",
        "",
        f"- `{format_command(metadata['command'])}`",
        "",
        "## Result",
        "",
        f"- Status: {status}",
        f"- Exit code: {metadata['exit_code']}",
        f"- Duration: {metadata['duration_seconds']}s",
        f"- CWD: `{metadata['cwd']}`",
        "",
        "## Logs",
        "",
        f"- Output: `{metadata['stdout_log']}`",
    ]
    if status != "passed":
        lines.extend(["", "This command did not complete successfully; do not claim the PR is verified."])
    return "\n".join(lines)


def capture_test_run(
    issue_ref: IssueRef,
    command: tuple[str, ...],
    workspace: Path | None = None,
    *,
    force: bool = False,
    timeout: int = 600,
) -> TestRunResult:
    validate_command(command)
    root = workspace_path(workspace)
    paths = pack_paths(issue_ref, root)
    require_valid_pack(paths, issue_ref.ref)
    ensure_pack_can_write(paths, ("test-run.json", "test-output.log", "test-run.md"), force=force)
    cwd = command_cwd(issue_ref, root)
    before_commit = git_output(cwd, ["rev-parse", "HEAD"])
    started_at = utc_now()
    started = time.monotonic()
    exit_code: int | None
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout)
        exit_code = result.returncode
        raw_output = (result.stdout or "") + (result.stderr or "")
        output = redact_text(raw_output)
        status = "passed" if exit_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        raw_output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        output = redact_text(raw_output)
        status = "timeout"
    finished_at = utc_now()
    duration = round(time.monotonic() - started, 3)
    dirty_status = git_output(cwd, ["status", "--porcelain"])
    after_commit = git_output(cwd, ["rev-parse", "HEAD"])
    commit_performed = bool(before_commit and after_commit and before_commit != after_commit)
    metadata: dict[str, object] = {
        "schema_version": 1,
        "kind": "opensense.test_run",
        "issue_ref": issue_ref.ref,
        "cwd": str(cwd),
        "command": list(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "exit_code": exit_code,
        "status": status,
        "stdout_log": "test-output.log",
        "output_truncated": False,
        "redaction_applied": output != raw_output,
        "base_commit": before_commit,
        "git_commit": after_commit,
        "dirty_status": dirty_status,
        "source_modified": bool(dirty_status),
        "git_commit_performed": commit_performed,
        "git_push_performed": "not_asserted",
        "github_write_performed": "not_asserted",
    }
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.test_output_log.write_text(output, encoding="utf-8", newline="\n")
    paths.test_run_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    paths.test_run_md.write_text(build_evidence(metadata).rstrip() + "\n", encoding="utf-8", newline="\n")
    return TestRunResult(
        issue_ref=issue_ref.ref,
        root=paths.root,
        status=status,
        exit_code=exit_code,
        written_files=(paths.test_run_json, paths.test_output_log, paths.test_run_md),
    )
