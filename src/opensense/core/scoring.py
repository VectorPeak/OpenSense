"""Deterministic issue scoring."""

from __future__ import annotations

from datetime import datetime

from opensense.models import Issue, IssueScore, utc_now


SMALL_LABELS = {
    "good first issue",
    "good-first-issue",
    "help wanted",
    "bug",
    "tests",
    "test",
    "documentation",
    "docs",
    "ci",
    "typing",
    "example",
    "examples",
}
LARGE_LABELS = {
    "feature",
    "enhancement",
    "design",
    "proposal",
    "rfc",
    "needs design",
    "architecture",
}


def clamp(value: int, lower: int = 0, upper: int = 100) -> int:
    return max(lower, min(upper, value))


def days_since(value: datetime | None, now: datetime | None = None) -> int | None:
    if value is None:
        return None
    current = now or utc_now()
    delta = current - value
    return max(0, delta.days)


def contribution_type(issue: Issue) -> str:
    labels = {label.lower() for label in issue.labels}
    title = issue.title.lower()
    if labels & {"test", "tests"} or "test" in title:
        return "test"
    if labels & {"documentation", "docs"} or "doc" in title:
        return "docs"
    if "ci" in labels or "ci" in title:
        return "ci"
    if "bug" in labels or "fix" in title or "bug" in title:
        return "bug fix"
    if labels & {"typing", "type"}:
        return "typing"
    return "small change"


def score_issue(
    issue: Issue,
    *,
    min_stars: int = 0,
    updated_days: int = 30,
    max_comments: int = 20,
    now: datetime | None = None,
) -> IssueScore:
    labels = {label.lower() for label in issue.labels}
    reasons: list[str] = []
    risks: list[str] = []

    opportunity = 50
    if issue.repository_stars >= min_stars:
        opportunity += 15
        reasons.append("repository meets star threshold")
    else:
        opportunity -= 20
        risks.append("repository is below the star threshold")

    age = days_since(issue.updated_at, now)
    if age is None:
        risks.append("missing update timestamp")
        opportunity -= 5
    elif age <= updated_days:
        opportunity += 20
        reasons.append("recently updated")
    else:
        opportunity -= 20
        risks.append("stale issue")

    if issue.assignees:
        opportunity -= 25
        risks.append("already assigned")
    else:
        opportunity += 10
        reasons.append("unassigned")

    smallness = 55
    if labels & SMALL_LABELS:
        smallness += 25
        reasons.append("has approachable labels")
    if labels & LARGE_LABELS:
        smallness -= 25
        risks.append("may require design or feature work")
    if issue.comments <= max_comments:
        smallness += 15
        reasons.append("discussion is not too noisy")
    else:
        smallness -= 20
        risks.append("large discussion thread")

    mergeability = 55
    if labels & {"help wanted", "good first issue", "good-first-issue"}:
        mergeability += 15
        reasons.append("maintainer-facing contribution label")
    if issue.assignees:
        mergeability -= 15
    if issue.comments > max_comments:
        mergeability -= 15

    opportunity = clamp(opportunity)
    smallness = clamp(smallness)
    mergeability = clamp(mergeability)
    total = round(opportunity * 0.4 + smallness * 0.35 + mergeability * 0.25)

    return IssueScore(
        issue=issue,
        total=clamp(total),
        opportunity=opportunity,
        smallness=smallness,
        mergeability=mergeability,
        contribution_type=contribution_type(issue),
        reasons=tuple(dict.fromkeys(reasons)),
        risks=tuple(dict.fromkeys(risks)),
    )
