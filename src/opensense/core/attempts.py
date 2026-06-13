"""Read-only helpers for local issue attempt artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opensense.config import state_dir, workspace_path
from opensense.core.agent_workflow import summarize_agent_status
from opensense.core.issue_ref import parse_issue_reference
from opensense.storage.packs import pack_paths


@dataclass(frozen=True)
class AttemptSummary:
    issue_ref: str
    root: Path
    status: str
    next_step: str
    updated_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_ref": self.issue_ref,
            "root": str(self.root),
            "status": self.status,
            "next_step": self.next_step,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class AttemptOpenResult:
    issue_ref: str
    root: Path
    pr_draft: Path | None
    agent_handoff: Path | None
    diffstat: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_ref": self.issue_ref,
            "root": str(self.root),
            "pr_draft": str(self.pr_draft) if self.pr_draft else None,
            "agent_handoff": str(self.agent_handoff) if self.agent_handoff else None,
            "diffstat": str(self.diffstat) if self.diffstat else None,
        }


def attempt_status_from_rows(rows: tuple[tuple[str, str, str], ...]) -> str:
    statuses = {step: status for step, status, _ in rows}
    if statuses.get("PR draft") == "ready":
        return "ready_for_human_review"
    if statuses.get("Tests") == "passed":
        return "ready_for_pr_draft"
    if statuses.get("Agent apply") == "passed":
        return "needs_tests"
    if statuses.get("Agent handoff") == "ready":
        return "ready_for_apply"
    if statuses.get("Sandbox") == "ready":
        return "needs_handoff"
    if statuses.get("Proposal") == "ready":
        return "needs_sandbox"
    return "needs_proposal"


def iter_attempt_roots(workspace: Path | None = None) -> list[Path]:
    packs_root = state_dir(workspace) / "packs"
    if not packs_root.exists():
        return []
    return [path for path in packs_root.glob("*/*") if path.is_dir()]


def issue_ref_from_attempt_root(root: Path) -> str | None:
    pack_json = root / "md_docs" / "pack.json"
    if pack_json.exists():
        try:
            import json

            pack = json.loads(pack_json.read_text(encoding="utf-8"))
            return str(pack.get("issue", {}).get("ref") or "") or None
        except Exception:
            return None
    if root.parent.name and root.name.isdigit():
        return f"{root.parent.name.replace('__', '/') }#{root.name}"
    return None


def list_attempts(workspace: Path | None = None, *, limit: int = 20) -> tuple[AttemptSummary, ...]:
    root = workspace_path(workspace)
    summaries: list[AttemptSummary] = []
    for attempt_root in iter_attempt_roots(root):
        issue_text = issue_ref_from_attempt_root(attempt_root)
        if not issue_text:
            continue
        try:
            issue_ref = parse_issue_reference(issue_text)
            status = summarize_agent_status(issue_ref, root)
            summary_status = attempt_status_from_rows(status.rows)
            next_step = status.next_step
        except Exception:
            summary_status = "invalid"
            next_step = "Inspect local pack artifacts manually."
        summaries.append(
            AttemptSummary(
                issue_ref=issue_text,
                root=attempt_root,
                status=summary_status,
                next_step=next_step,
                updated_at=attempt_root.stat().st_mtime,
            )
        )
    return tuple(sorted(summaries, key=lambda item: item.updated_at, reverse=True)[:limit])


def open_attempt(issue_text: str, workspace: Path | None = None) -> AttemptOpenResult:
    root = workspace_path(workspace)
    issue_ref = parse_issue_reference(issue_text)
    paths = pack_paths(issue_ref, root)
    if not paths.root.exists():
        raise FileNotFoundError("Attempt not found. Run `opensense pack <issue-url>` first.")
    return AttemptOpenResult(
        issue_ref=issue_ref.ref,
        root=paths.root,
        pr_draft=paths.pr_draft_md if paths.pr_draft_md.exists() else None,
        agent_handoff=paths.agent_handoff_md if paths.agent_handoff_md.exists() else None,
        diffstat=paths.diffstat_txt if paths.diffstat_txt.exists() else None,
    )
