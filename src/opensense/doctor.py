"""Local health checks."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from opensense.config import config_path, state_dir, watchlist_path


@dataclass(frozen=True)
class Check:
    status: str
    name: str
    detail: str


def looks_like_raw_secret(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("ghp_", "github_pat_", "sk-", "sk_")) or "api_key =" in lowered


def run_checks(workspace: Path | None = None) -> list[Check]:
    root = state_dir(workspace)
    checks: list[Check] = []

    if root.is_dir():
        checks.append(Check("OK", "state directory", str(root)))
    else:
        return [Check("ERROR", "state directory", f"{root} is missing; run `opensense init`.")]

    cfg = config_path(workspace)
    watch = watchlist_path(workspace)
    for path, label in ((cfg, "config.toml"), (watch, "watchlist.toml")):
        if path.exists():
            checks.append(Check("OK", label, "present"))
        else:
            checks.append(Check("ERROR", label, "missing"))

    for dirname in ("cache", "reports"):
        path = root / dirname
        checks.append(Check("OK" if path.is_dir() else "ERROR", dirname, "present" if path.is_dir() else "missing"))

    if cfg.exists():
        raw = cfg.read_text(encoding="utf-8")
        if any(looks_like_raw_secret(line.strip()) for line in raw.splitlines()):
            checks.append(Check("ERROR", "secret storage", "config appears to contain a raw secret"))
        else:
            checks.append(Check("OK", "secret storage", "config stores environment variable names only"))

        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError as exc:
            checks.append(Check("ERROR", "config.toml", f"invalid TOML: {exc}"))
            return checks
        github_env = str(data.get("auth", {}).get("github_token_env", "GITHUB_TOKEN"))
        llm_env = str(data.get("llm", {}).get("api_key_env", "OPENSENSE_LLM_API_KEY"))
        checks.append(
            Check(
                "OK" if os.environ.get(github_env) else "WARN",
                "GitHub token env",
                f"{github_env} is {'set' if os.environ.get(github_env) else 'not set'}",
            )
        )
        checks.append(
            Check(
                "OK" if os.environ.get(llm_env) else "WARN",
                "LLM API key env",
                f"{llm_env} is {'set' if os.environ.get(llm_env) else 'not set'}; LLM is optional",
            )
        )

    return checks


def has_errors(checks: list[Check]) -> bool:
    return any(check.status == "ERROR" for check in checks)
