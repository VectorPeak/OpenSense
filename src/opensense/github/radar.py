"""GitHub-backed radar signals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from opensense.core.radar import score_radar
from opensense.github.client import GitHubClient
from opensense.models import RadarResult


def fetch_radar(client: GitHubClient, repo: str, *, skills: tuple[str, ...] = (), stale_days: int = 30) -> RadarResult:
    metadata = client.get_json(f"/repos/{repo}")
    languages = tuple((client.get_json(f"/repos/{repo}/languages") or {}).keys())
    prs = client.get_json(
        f"/repos/{repo}/pulls",
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": 100},
    )
    issues = client.get_json(f"/repos/{repo}/issues", {"state": "open", "per_page": 1})

    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    merged = 0
    external_merged = 0
    open_prs = 0
    stale_prs = 0
    repo_owner = repo.split("/", 1)[0].lower()
    for pr in prs:
        if pr.get("state") == "open":
            open_prs += 1
            updated_at = str(pr.get("updated_at", "")).replace("Z", "+00:00")
            try:
                if datetime.fromisoformat(updated_at) < cutoff:
                    stale_prs += 1
            except ValueError:
                pass
        if pr.get("merged_at"):
            merged += 1
            user = (pr.get("user") or {}).get("login", "")
            if str(user).lower() != repo_owner:
                external_merged += 1

    return score_radar(
        repo,
        stars=int(metadata.get("stargazers_count") or 0),
        open_issues=len(issues),
        open_prs=open_prs,
        merged_prs=merged,
        stale_prs=stale_prs,
        external_merged_prs=external_merged,
        languages=languages,
        skills=skills,
    )
