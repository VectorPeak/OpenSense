"""Configuration file helpers for OpenSense."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STATE_DIR_NAME = ".opensense"
ENV_VAR_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
DEFAULT_REPOSITORIES = (
    "openclaw/openclaw",
    "vllm-project/vllm",
    "openai/codex",
    "sgl-project/sglang",
    "langchain-ai/langchain",
    "run-llama/llama_index",
)
DEFAULT_SKILLS = ("agent", "rag")


@dataclass(frozen=True)
class OpenSenseConfig:
    github_token_env: str = "GITHUB_TOKEN"
    llm_provider: str = "openai-compatible"
    llm_base_url_env: str = "OPENSENSE_LLM_BASE_URL"
    llm_api_key_env: str = "OPENSENSE_LLM_API_KEY"
    llm_model_env: str = "OPENSENSE_LLM_MODEL"
    cache_dir: str = "cache"
    reports_dir: str = "reports"


def workspace_path(workspace: Path | None = None) -> Path:
    return (workspace or Path.cwd()).resolve()


def state_dir(workspace: Path | None = None) -> Path:
    return workspace_path(workspace) / STATE_DIR_NAME


def config_path(workspace: Path | None = None) -> Path:
    return state_dir(workspace) / "config.toml"


def watchlist_path(workspace: Path | None = None) -> Path:
    return state_dir(workspace) / "watchlist.toml"


def default_llm_base_url() -> str:
    return os.environ.get("OPENSENSE_LLM_BASE_URL", "https://api.openai.com/v1")


def default_llm_model() -> str:
    return os.environ.get("OPENSENSE_LLM_MODEL", "gpt-5.5")


def looks_like_raw_secret(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("ghp_", "github_pat_", "sk-", "sk_"))


def validate_env_var_name(value: str, option_name: str) -> str:
    candidate = value.strip()
    if looks_like_raw_secret(candidate):
        raise ValueError(f"{option_name} expects an environment variable name, not a raw secret.")
    if not ENV_VAR_RE.match(candidate):
        raise ValueError(f"{option_name} must be an uppercase environment variable name, such as OPENAI_API_KEY.")
    return candidate


def render_config(config: OpenSenseConfig) -> str:
    return "\n".join(
        [
            "[auth]",
            f'github_token_env = "{config.github_token_env}"',
            f'llm_api_key_env = "{config.llm_api_key_env}"',
            "",
            "[llm]",
            f'provider = "{config.llm_provider}"',
            f'base_url_env = "{config.llm_base_url_env}"',
            f'api_key_env = "{config.llm_api_key_env}"',
            f'model_env = "{config.llm_model_env}"',
            "",
            "[paths]",
            f'cache_dir = "{config.cache_dir}"',
            f'reports_dir = "{config.reports_dir}"',
            "",
        ]
    )


def render_default_watchlist() -> str:
    quoted_skills = ", ".join(f'"{skill}"' for skill in DEFAULT_SKILLS)
    lines = [f"skills = [{quoted_skills}]", ""]
    for repo in DEFAULT_REPOSITORIES:
        lines.extend(["[[repositories]]", f'name = "{repo}"', ""])
    return "\n".join(lines).rstrip() + "\n"


def initialize_state(workspace: Path | None, config: OpenSenseConfig, force: bool = False) -> Path:
    root = state_dir(workspace)
    root.mkdir(parents=True, exist_ok=True)
    (root / config.cache_dir).mkdir(parents=True, exist_ok=True)
    (root / config.reports_dir).mkdir(parents=True, exist_ok=True)

    cfg_path = root / "config.toml"
    if force or not cfg_path.exists():
        cfg_path.write_text(render_config(config), encoding="utf-8", newline="\n")

    watch_path = root / "watchlist.toml"
    if force or not watch_path.exists():
        watch_path.write_text(render_default_watchlist(), encoding="utf-8", newline="\n")

    return root


def load_config(workspace: Path | None = None) -> dict[str, Any]:
    path = config_path(workspace)
    if not path.exists():
        raise FileNotFoundError("OpenSense is not initialized. Run `opensense init` first.")
    return tomllib.loads(path.read_text(encoding="utf-8"))
