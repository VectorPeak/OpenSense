"""Lightweight secret-pattern checks for generated artifacts."""

from __future__ import annotations

import re


SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
)


def contains_secret_like_text(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def assert_no_secret_like_text(value: str, *, source: str) -> None:
    if contains_secret_like_text(value):
        raise ValueError(f"Potential secret detected in {source}; refusing to write pack artifact.")
