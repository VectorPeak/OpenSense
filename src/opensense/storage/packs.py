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
    index_md: Path
    docs_dir: Path
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


PACK_INDEX_FILENAME = "index.md"

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
    docs_dir = root / "md_docs"
    return PackPaths(
        root=root,
        index_md=root / PACK_INDEX_FILENAME,
        docs_dir=docs_dir,
        issue_md=docs_dir / "issue.md",
        repo_md=docs_dir / "repo.md",
        files_md=docs_dir / "files.md",
        tests_md=docs_dir / "tests.md",
        plan_md=docs_dir / "plan.md",
        risks_md=docs_dir / "risks.md",
        agent_md=docs_dir / "agent.md",
        pr_summary_md=root / "pr-summary.md",
        test_evidence_md=root / "test-evidence.md",
        maintainer_note_md=root / "maintainer-note.md",
        pack_json=docs_dir / "pack.json",
        manifest_json=docs_dir / "manifest.json",
        sandbox_json=root / "sandbox.json",
        patch_proposal_md=docs_dir / "patch-proposal.md",
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


def pack_artifact_path(paths: PackPaths, filename: str) -> Path:
    if filename == PACK_INDEX_FILENAME:
        return paths.index_md
    if filename in PACK_ARTIFACT_FILENAMES or filename == "patch-proposal.md":
        return paths.docs_dir / filename
    return paths.root / filename


def ensure_pack_can_write(paths: PackPaths, filenames: tuple[str, ...], *, force: bool = False) -> None:
    if force:
        return
    existing = [name for name in filenames if pack_artifact_path(paths, name).exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Pack files already exist: {joined}. Re-run with --force to overwrite.")


def write_markdown_files(paths: PackPaths, files: dict[str, str], *, force: bool = False, prechecked: bool = False) -> tuple[Path, ...]:
    if not prechecked:
        ensure_pack_can_write(paths, tuple(files), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in files.items():
        target = pack_artifact_path(paths, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
        written.append(target)
    return tuple(written)


def write_json_files(paths: PackPaths, files: dict[str, dict[str, object]], *, force: bool = False, prechecked: bool = False) -> tuple[Path, ...]:
    if not prechecked:
        ensure_pack_can_write(paths, tuple(files), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in files.items():
        target = pack_artifact_path(paths, name)
        target.parent.mkdir(parents=True, exist_ok=True)
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
    missing = [name for name in PACK_FILENAMES if not pack_artifact_path(paths, name).exists()]
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
