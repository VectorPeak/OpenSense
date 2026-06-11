"""Read-only patch suitability evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from opensense.core.scoring import score_issue
from opensense.models import Issue


SENSITIVE_TERMS = ("security", "auth", "privacy", "payment", "license", "legal", "encryption")
LARGE_TERMS = ("architecture", "migration", "refactor", "design", "rfc", "breaking")


@dataclass(frozen=True)
class PatchDryRunResult:
    feasible: bool
    confidence: str
    risks: tuple[str, ...]
    required_context: tuple[str, ...]
    suggested_steps: tuple[str, ...]


def patch_dry_run(issue: Issue) -> PatchDryRunResult:
    score = score_issue(issue)
    text = " ".join((issue.title, " ".join(issue.labels))).lower()
    risks = list(score.risks)
    required_context = [
        "Read the full issue thread and linked discussions.",
        "Check README, CONTRIBUTING, issue templates, and PR templates.",
        "Find a narrow reproduction or verification path.",
    ]
    suggested_steps = [
        "Generate or refresh the context pack.",
        "Inspect the smallest likely module first.",
        "Add or run a focused regression test before changing behavior.",
        "Keep the patch under five files and roughly 300 changed lines.",
    ]

    feasible = score.total >= 65
    confidence = "medium" if feasible else "low"

    if issue.assignees:
        feasible = False
        confidence = "low"
        risks.append("issue is already assigned")
    if issue.state.lower() != "open":
        feasible = False
        confidence = "blocked"
        risks.append(f"issue state is {issue.state}; only open issues are suitable for patch dry-run")
    if any(term in text for term in SENSITIVE_TERMS):
        feasible = False
        confidence = "blocked"
        risks.append("sensitive topic should stay human-only")
    if any(term in text for term in LARGE_TERMS):
        feasible = False
        confidence = "low"
        risks.append("likely requires broad design or architecture work")
    if issue.comments > 20:
        required_context.append("Summarize the discussion before any coding-agent handoff.")

    return PatchDryRunResult(
        feasible=feasible,
        confidence=confidence,
        risks=tuple(dict.fromkeys(risks)) or ("no major dry-run risk found",),
        required_context=tuple(required_context),
        suggested_steps=tuple(suggested_steps),
    )
