"""Daily candidate summaries and LLM analysis."""

from __future__ import annotations

from opensense.llm.client import LLMConfig, chat_completion, has_llm_key
from opensense.models import IssueScore


def daily_analysis_prompt(ranked: list[IssueScore], skills: tuple[str, ...] = ()) -> str:
    lines = [
        "Analyze these ranked GitHub issue candidates for today's open-source contribution work.",
        "",
        f"Watched skills: {', '.join(skills) or 'none'}",
        "",
        "Candidates:",
    ]
    for index, item in enumerate(ranked, start=1):
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
        "Return concise Markdown in Chinese with: best first pick, why, risks to check, and the exact next opensense issue command."
    )
    return "\n".join(lines)


def generate_daily_analysis(ranked: list[IssueScore], skills: tuple[str, ...], config: LLMConfig | None) -> str:
    if not ranked:
        return "No daily candidates to analyze."
    if not config or not has_llm_key(config):
        return "LLM analysis skipped: no LLM API key is configured."
    return chat_completion(config, daily_analysis_prompt(ranked, skills))
