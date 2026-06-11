"""PR evidence generation from an existing context pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opensense.core.issue_ref import IssueRef
from opensense.storage.packs import EVIDENCE_FILENAMES, pack_paths, require_valid_pack, write_markdown_files


@dataclass(frozen=True)
class EvidenceResult:
    issue_ref: IssueRef
    root: Path
    written_files: tuple[Path, ...]


@dataclass(frozen=True)
class EvidenceBundle:
    issue_ref: IssueRef
    files: dict[str, str]


def build_evidence_bundle(issue_ref: IssueRef) -> EvidenceBundle:
    files = {
        "pr-summary.md": f"""# PR Summary Draft

Related issue: {issue_ref.url}

## Summary

- Proposed change: not written yet.
- Scope: keep the PR small and tied to `{issue_ref.ref}`.

## Evidence Required Before PR

- Reproduction or verification steps.
- Test commands with real exit codes.
- Risk and limitation notes.

## Important

This is a draft. Do not claim a fix is complete until code has been changed and verified.
""",
        "test-evidence.md": """# Test Evidence

## Commands Run

- Not run.

## Result

- Not verified.

Only replace this section with real command output after tests have actually run.
""",
        "maintainer-note.md": f"""# Maintainer Note Draft

I am looking at {issue_ref.ref} and planning a small, focused change.

Before opening a PR, I will verify the behavior locally, keep the diff narrow, and include test evidence in the PR description.

Open questions:

- Is this issue still available for an external contributor?
- Is there a preferred test or module to inspect first?
""",
    }
    return EvidenceBundle(issue_ref=issue_ref, files=files)


def evidence_files(issue_ref: IssueRef) -> dict[str, str]:
    return build_evidence_bundle(issue_ref).files


def generate_evidence(issue_ref: IssueRef, workspace: Path | None = None, *, force: bool = False) -> EvidenceResult:
    paths = pack_paths(issue_ref, workspace)
    require_valid_pack(paths, issue_ref.ref)
    bundle = build_evidence_bundle(issue_ref)
    written = write_markdown_files(paths, bundle.files, force=force)
    expected = {paths.root / name for name in EVIDENCE_FILENAMES}
    return EvidenceResult(issue_ref=issue_ref, root=paths.root, written_files=tuple(path for path in written if path in expected))
