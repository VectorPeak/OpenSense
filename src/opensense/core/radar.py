"""Lightweight repository contribution radar."""

from __future__ import annotations

from opensense.models import RadarResult


def recommendation(score: int) -> str:
    if score >= 75:
        return "Go"
    if score >= 60:
        return "Watch"
    if score >= 45:
        return "Comment first"
    return "Avoid for now"


def score_radar(
    repository: str,
    *,
    stars: int = 0,
    open_issues: int = 0,
    open_prs: int = 0,
    merged_prs: int = 0,
    stale_prs: int = 0,
    external_merged_prs: int = 0,
    languages: tuple[str, ...] = (),
    skills: tuple[str, ...] = (),
) -> RadarResult:
    score = 45
    reasons: list[str] = []
    risks: list[str] = []

    if stars >= 500:
        score += 10
        reasons.append("widely used repository")
    if merged_prs >= 10:
        score += 20
        reasons.append("healthy recent merge activity")
    elif merged_prs >= 3:
        score += 10
        reasons.append("some recent PRs were merged")
    else:
        risks.append("low recent merge activity")
        score -= 10

    if open_prs > 0 and stale_prs / max(open_prs, 1) > 0.5:
        score -= 15
        risks.append("many open PRs look stale")
    if external_merged_prs >= 3:
        score += 15
        reasons.append("external contributors are getting merged")
    elif external_merged_prs == 0:
        score -= 10
        risks.append("no recent external contributor merges found")

    lower_languages = {item.lower() for item in languages}
    lower_skills = {item.lower() for item in skills}
    if lower_skills and lower_languages & lower_skills:
        score += 10
        reasons.append("language matches your skills")

    score = max(0, min(100, score))
    return RadarResult(
        repository=repository,
        score=score,
        recommendation=recommendation(score),
        stars=stars,
        open_issues=open_issues,
        open_prs=open_prs,
        merged_prs=merged_prs,
        stale_prs=stale_prs,
        external_merged_prs=external_merged_prs,
        languages=languages,
        reasons=tuple(reasons),
        risks=tuple(risks),
    )
