"""Daily candidate summaries and LLM-assisted finding."""

from __future__ import annotations

from opensense.llm.client import LLMConfig, chat_completion, has_llm_key
from opensense.models import IssueScore


def daily_analysis_prompt(candidates: list[IssueScore], skills: tuple[str, ...] = (), display_limit: int = 10) -> str:
    lines = [
        "You are helping a developer find the best GitHub issue to work on today.",
        "The issues below are a candidate pool collected from watched repositories.",
        "Use the rule scores as hints, but make your own prioritization based on likely PR size, clarity, maintainer risk, and skill fit.",
        "",
        f"Watched skills: {', '.join(skills) or 'none'}",
        f"Requested shortlist size: {display_limit}",
        "",
        "Candidate pool:",
    ]
    for index, item in enumerate(candidates, start=1):
        issue = item.issue
        lines.extend(
            [
                f"{index}. {issue.ref}",
                f"   Title: {issue.title}",
                f"   Score: {item.total}",
                f"   Type: {item.contribution_type}",
                f"   Labels: {', '.join(issue.labels) or 'none'}",
                f"   Reasons: {', '.join(item.reasons) or 'none'}",
                f"   Risks: {', '.join(item.risks) or 'none'}",
                "",
            ]
        )
    lines.append(
        "Return concise Markdown in Chinese with: top 3 picks, why each is a good first target, risks to check before coding, and exact next opensense issue commands."
    )
    return "\n".join(lines)


def generate_daily_analysis(
    candidates: list[IssueScore],
    skills: tuple[str, ...],
    config: LLMConfig | None,
    display_limit: int = 10,
) -> str:
    if not candidates:
        return "No daily candidates to analyze."
    if not config or not has_llm_key(config):
        return "LLM analysis skipped: no LLM API key is configured."
    return chat_completion(config, daily_analysis_prompt(candidates, skills, display_limit))
