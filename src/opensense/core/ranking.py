"""Issue ranking helpers."""

from __future__ import annotations

from dataclasses import replace

from opensense.core.scoring import score_issue
from opensense.models import Issue, IssueScore


def matching_skills(issue: Issue, skills: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return watched skills that appear in issue text or labels."""

    text = " ".join((issue.title, issue.body, " ".join(issue.labels))).lower()
    return tuple(skill for skill in skills if skill.lower() in text)


def apply_skill_boost(score: IssueScore, skills: tuple[str, ...] = ()) -> IssueScore:
    matches = matching_skills(score.issue, skills)
    if not matches:
        return score
    return replace(
        score,
        total=min(100, score.total + 10),
        reasons=(f"matches watched skill: {', '.join(matches[:3])}", *score.reasons),
    )


def rank_issues(
    issues: list[Issue],
    *,
    limit: int = 10,
    min_stars: int = 0,
    updated_days: int = 30,
    max_comments: int = 20,
    skills: tuple[str, ...] = (),
) -> list[IssueScore]:
    scored = [
        apply_skill_boost(
            score_issue(issue, min_stars=min_stars, updated_days=updated_days, max_comments=max_comments),
            skills=skills,
        )
        for issue in issues
        if issue.comments <= max_comments and issue.repository_stars >= min_stars
    ]
    scored.sort(key=lambda item: (-item.total, -item.issue.repository_stars, item.issue.ref.lower()))
    return scored[:limit]
