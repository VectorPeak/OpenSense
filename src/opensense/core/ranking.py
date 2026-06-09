"""Issue ranking helpers."""

from __future__ import annotations

from opensense.core.scoring import score_issue
from opensense.models import Issue, IssueScore


def rank_issues(
    issues: list[Issue],
    *,
    limit: int = 10,
    min_stars: int = 0,
    updated_days: int = 30,
    max_comments: int = 20,
) -> list[IssueScore]:
    scored = [
        score_issue(issue, min_stars=min_stars, updated_days=updated_days, max_comments=max_comments)
        for issue in issues
        if issue.comments <= max_comments and issue.repository_stars >= min_stars
    ]
    scored.sort(key=lambda item: (-item.total, -item.issue.repository_stars, item.issue.ref.lower()))
    return scored[:limit]
