"""GitHub issue reference parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from opensense.storage.watchlist import validate_repo_name


ISSUE_URL_RE = re.compile(r"^https://github\.com/([^/\s]+)/([^/\s]+)/issues/([1-9][0-9]*)(?:[?#].*)?$")


@dataclass(frozen=True)
class IssueRef:
    owner: str
    repo: str
    number: int

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def ref(self) -> str:
        return f"{self.repository}#{self.number}"

    @property
    def slug(self) -> str:
        return f"{self.owner}__{self.repo}/{self.number}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}/issues/{self.number}"


def parse_issue_reference(value: str) -> IssueRef:
    text = value.strip()
    match = ISSUE_URL_RE.match(text)
    if match:
        owner, repo, number_text = match.groups()
        return IssueRef(owner=owner, repo=repo, number=int(number_text))

    if "/pull/" in text:
        raise ValueError("Issue reference must point to a GitHub issue, not a pull request.")
    if "#" not in text:
        raise ValueError("Issue must use owner/repo#number or https://github.com/owner/repo/issues/number.")
    repo_text, number_text = text.rsplit("#", 1)
    try:
        repository = validate_repo_name(repo_text)
    except ValueError as exc:
        raise ValueError("Issue must use owner/repo#number format.") from exc
    try:
        number = int(number_text)
    except ValueError as exc:
        raise ValueError("Issue number must be an integer.") from exc
    if number <= 0:
        raise ValueError("Issue number must be greater than zero.")
    owner, repo = repository.split("/", 1)
    return IssueRef(owner=owner, repo=repo, number=number)
