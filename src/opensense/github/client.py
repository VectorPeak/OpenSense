"""Small GitHub REST client built on the standard library."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


API_ROOT = "https://api.github.com"


@dataclass(frozen=True)
class GitHubClient:
    token_env: str = "GITHUB_TOKEN"
    api_root: str = API_ROOT

    @property
    def token(self) -> str | None:
        return os.environ.get(self.token_env)

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = self.api_root.rstrip("/") + "/" + path.lstrip("/")
        if query:
            url += "?" + query

        request = urllib.request.Request(url)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "OpenSense")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")

        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
