"""GitHub issue fetching."""

from __future__ import annotations

from opensense.github.client import GitHubClient
from opensense.models import Issue


def repo_stars(client: GitHubClient, repo: str) -> int:
    data = client.get_json(f"/repos/{repo}")
    return int(data.get("stargazers_count") or 0)


def fetch_open_issues(
    client: GitHubClient,
    repo: str,
    *,
    limit: int = 30,
    labels: tuple[str, ...] = (),
) -> list[Issue]:
    owner, name = repo.split("/", 1)
    stars = repo_stars(client, repo)
    params: dict[str, object] = {
        "state": "open",
        "sort": "updated",
        "direction": "desc",
        "per_page": min(max(limit, 1), 100),
    }
    if labels:
        params["labels"] = ",".join(labels)
    payloads = client.get_json(f"/repos/{repo}/issues", params)
    issues: list[Issue] = []
    for payload in payloads:
        if "pull_request" in payload:
            continue
        issues.append(Issue.from_github(owner, name, payload, repository_stars=stars))
    return issues
