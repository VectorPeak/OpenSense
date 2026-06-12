"""Patch proposal generation from a validated context pack."""

from __future__ import annotations

from pathlib import Path

from opensense.core.issue_ref import IssueRef
from opensense.storage.packs import ensure_pack_can_write, pack_paths, require_valid_pack


def proposal_markdown(pack: dict) -> str:
    issue = pack.get("issue", {})
    facts = pack.get("facts", {})
    inferences = pack.get("inferences", {})
    risks = pack.get("risks", [])
    unknowns = pack.get("unknowns", [])
    test_guidance = pack.get("test_guidance", {})
    constraints = pack.get("agent_constraints", [])
    searches = inferences.get("candidate_file_searches", [])
    commands = test_guidance.get("suggested_commands", [])
    return "\n".join(
        [
            "# Patch Proposal",
            "",
            f"Issue: {issue.get('ref', 'unknown')}",
            f"Title: {issue.get('title', 'unknown')}",
            f"Contribution type: {inferences.get('contribution_type', 'unknown')}",
            f"Score: {inferences.get('score', 'unknown')}",
            f"Repository: {facts.get('repository', 'unknown')}",
            "",
            "## Target Files To Inspect",
            *(f"- {item}" for item in searches),
            *(["- No target file is known yet; inspect the issue and search locally first."] if not searches else []),
            "",
            "## Likely Smallest Change",
            "- Reproduce or verify the reported behavior before editing.",
            "- Make the narrowest change that addresses this issue only.",
            "- Prefer adding or updating a focused regression test.",
            "",
            "## Tests To Run",
            *(f"- {item}" for item in commands),
            *(["- Not known yet. Read repository test instructions before coding."] if not commands else []),
            "",
            "## Stop Conditions",
            "- Stop if the issue is already assigned or covered by an active PR.",
            "- Stop if the change touches auth, security, privacy, payment, license, or legal logic.",
            "- Stop if the expected change grows beyond five files or roughly 300 changed lines.",
            "- Stop if no reproduction or verification path can be found.",
            "",
            "## Risks",
            *(f"- {item}" for item in risks),
            *(["- No rule-based risk was recorded in pack.json."] if not risks else []),
            "",
            "## Unknowns",
            *(f"- {item}" for item in unknowns),
            "",
            "## Agent Constraints",
            *(f"- {item}" for item in constraints),
            "",
            "## PR Evidence Required",
            "- Real test commands and exit codes.",
            "- A concise explanation of why the patch fixes the issue.",
            "- Clear limitations and anything not verified.",
        ]
    )


def generate_patch_proposal(issue_ref: IssueRef, workspace: Path | None = None, *, force: bool = False) -> Path:
    paths = pack_paths(issue_ref, workspace)
    payload = require_valid_pack(paths, issue_ref.ref)
    ensure_pack_can_write(paths, ("patch-proposal.md",), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.patch_proposal_md.write_text(proposal_markdown(payload["pack"]).rstrip() + "\n", encoding="utf-8", newline="\n")
    return paths.patch_proposal_md
