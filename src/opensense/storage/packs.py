"""Storage helpers for OpenSense context packs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

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
    pack_json: Path
    manifest_json: Path
    sandbox_json: Path
    patch_proposal_md: Path
    test_run_json: Path
    test_run_md: Path
    test_output_log: Path
    pr_draft_json: Path
    pr_draft_md: Path
    agent_handoff_json: Path
    agent_handoff_md: Path
    agent_apply_json: Path
    agent_output_log: Path
    diff_patch: Path
    diffstat_txt: Path


PACK_FILENAMES = (
    "issue.md",
    "repo.md",
    "files.md",
    "tests.md",
    "plan.md",
    "risks.md",
    "agent.md",
)

STRUCTURED_PACK_FILENAMES = (
    "pack.json",
    "manifest.json",
)

PACK_ARTIFACT_FILENAMES = (*PACK_FILENAMES, *STRUCTURED_PACK_FILENAMES)

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
        pack_json=root / "pack.json",
        manifest_json=root / "manifest.json",
        sandbox_json=root / "sandbox.json",
        patch_proposal_md=root / "patch-proposal.md",
        test_run_json=root / "test-run.json",
        test_run_md=root / "test-run.md",
        test_output_log=root / "test-output.log",
        pr_draft_json=root / "pr-draft.json",
        pr_draft_md=root / "pr-draft.md",
        agent_handoff_json=root / "agent-handoff.json",
        agent_handoff_md=root / "agent-handoff.md",
        agent_apply_json=root / "agent-apply.json",
        agent_output_log=root / "agent-output.log",
        diff_patch=root / "diff.patch",
        diffstat_txt=root / "diffstat.txt",
    )


def ensure_pack_can_write(paths: PackPaths, filenames: tuple[str, ...], *, force: bool = False) -> None:
    if force:
        return
    existing = [name for name in filenames if (paths.root / name).exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Pack files already exist: {joined}. Re-run with --force to overwrite.")


def write_markdown_files(paths: PackPaths, files: dict[str, str], *, force: bool = False, prechecked: bool = False) -> tuple[Path, ...]:
    if not prechecked:
        ensure_pack_can_write(paths, tuple(files), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in files.items():
        target = paths.root / name
        target.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
        written.append(target)
    return tuple(written)


def write_json_files(paths: PackPaths, files: dict[str, dict[str, object]], *, force: bool = False, prechecked: bool = False) -> tuple[Path, ...]:
    if not prechecked:
        ensure_pack_can_write(paths, tuple(files), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in files.items():
        target = paths.root / name
        target.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        written.append(target)
    return tuple(written)


def write_pack_artifacts(
    paths: PackPaths,
    markdown_files: dict[str, str],
    json_files: dict[str, dict[str, object]],
    *,
    force: bool = False,
) -> tuple[Path, ...]:
    ensure_pack_can_write(paths, (*tuple(markdown_files), *tuple(json_files)), force=force)
    return (
        *write_markdown_files(paths, markdown_files, force=force, prechecked=True),
        *write_json_files(paths, json_files, force=force, prechecked=True),
    )


def require_existing_pack(paths: PackPaths) -> None:
    missing = [name for name in PACK_FILENAMES if not (paths.root / name).exists()]
    if missing:
        raise FileNotFoundError("Context pack not found. Run `opensense pack <issue-url>` first.")


def load_pack_payload(paths: PackPaths) -> dict[str, Any]:
    if not paths.pack_json.exists() or not paths.manifest_json.exists():
        raise FileNotFoundError("Structured context pack not found. Run `opensense pack <issue-url>` first.")
    return {
        "pack": json.loads(paths.pack_json.read_text(encoding="utf-8")),
        "manifest": json.loads(paths.manifest_json.read_text(encoding="utf-8")),
    }


def validate_pack_payload(payload: dict[str, Any], requested_ref: str) -> None:
    pack = payload.get("pack", {})
    manifest = payload.get("manifest", {})
    pack_ref = str(pack.get("issue", {}).get("ref") or "")
    manifest_ref = str(manifest.get("issue_ref") or "")
    if manifest.get("kind") != "opensense.pack_manifest":
        raise ValueError("Pack manifest is missing the expected kind.")
    if pack_ref != requested_ref or manifest_ref != requested_ref:
        raise ValueError("Pack issue reference does not match the requested issue.")
    if manifest.get("secret_scan", {}).get("status") != "passed":
        raise ValueError("Pack secret scan has not passed.")
    safety = manifest.get("safety", {})
    if safety.get("source_modified") is not False or safety.get("github_write_performed") is not False:
        raise ValueError("Pack safety metadata is not read-only.")


def require_valid_pack(paths: PackPaths, requested_ref: str) -> dict[str, Any]:
    require_existing_pack(paths)
    payload = load_pack_payload(paths)
    validate_pack_payload(payload, requested_ref)
    return payload
