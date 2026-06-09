"""Shared data models for OpenSense."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class Issue:
    owner: str
    repo: str
    number: int
    title: str
    body: str = ""
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()
    comments: int = 0
    updated_at: datetime | None = None
    created_at: datetime | None = None
    html_url: str = ""
    repository_stars: int = 0
    state: str = "open"

    @property
    def ref(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"

    @classmethod
    def from_github(cls, owner: str, repo: str, payload: dict, repository_stars: int = 0) -> "Issue":
        labels = tuple(str(item.get("name", "")) for item in payload.get("labels", []) if item.get("name"))
        assignees = tuple(str(item.get("login", "")) for item in payload.get("assignees", []) if item.get("login"))
        return cls(
            owner=owner,
            repo=repo,
            number=int(payload["number"]),
            title=str(payload.get("title") or ""),
            body=str(payload.get("body") or ""),
            labels=labels,
            assignees=assignees,
            comments=int(payload.get("comments") or 0),
            updated_at=parse_github_datetime(payload.get("updated_at")),
            created_at=parse_github_datetime(payload.get("created_at")),
            html_url=str(payload.get("html_url") or ""),
            repository_stars=repository_stars,
            state=str(payload.get("state") or "open"),
        )


@dataclass(frozen=True)
class IssueScore:
    issue: Issue
    total: int
    opportunity: int
    smallness: int
    mergeability: int
    contribution_type: str
    reasons: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


@dataclass(frozen=True)
class RadarResult:
    repository: str
    score: int
    recommendation: str
    stars: int = 0
    open_issues: int = 0
    open_prs: int = 0
    merged_prs: int = 0
    stale_prs: int = 0
    external_merged_prs: int = 0
    languages: tuple[str, ...] = ()
    reasons: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
