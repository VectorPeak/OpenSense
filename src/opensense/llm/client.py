"""OpenAI-compatible LLM client."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    api_key_env: str = "OPENSENSE_LLM_API_KEY"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.5"


def config_from_env(
    *,
    api_key_env: str = "OPENSENSE_LLM_API_KEY",
    base_url_env: str = "OPENSENSE_LLM_BASE_URL",
    model_env: str = "OPENSENSE_LLM_MODEL",
) -> LLMConfig:
    return LLMConfig(
        api_key_env=api_key_env,
        base_url=os.environ.get(base_url_env, "https://api.openai.com/v1"),
        model=os.environ.get(model_env, "gpt-5.5"),
    )


def has_llm_key(config: LLMConfig) -> bool:
    return bool(os.environ.get(config.api_key_env))


def chat_completion(config: LLMConfig, prompt: str) -> str:
    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        raise RuntimeError(f"{config.api_key_env} is not set")

    body = json.dumps(
        {
            "model": config.model,
            "messages": [
                {"role": "system", "content": "You are an open-source contribution planning assistant."},
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(config.base_url.rstrip("/") + "/chat/completions", data=body, method="POST")
    request.add_header("Authorization", f"Bearer {api_key}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload["choices"][0]["message"]["content"]).strip()
