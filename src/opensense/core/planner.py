"""PR plan generation."""

from __future__ import annotations

from opensense.llm.client import LLMConfig, chat_completion, has_llm_key
from opensense.models import IssueScore


def rule_based_plan(score: IssueScore) -> str:
    issue = score.issue
    reasons = "\n".join(f"- {item}" for item in score.reasons) or "- No strong positive signal found."
    risks = "\n".join(f"- {item}" for item in score.risks) or "- No major risk found by rules."
    return "\n".join(
        [
            f"# PR Plan for {issue.ref}",
            "",
            f"Type: {score.contribution_type}",
            f"Score: {score.total}",
            "",
            "## Why This Looks Approachable",
            reasons,
            "",
            "## Risks",
            risks,
            "",
            "## Suggested Steps",
            "- Read the full issue thread and linked discussions.",
            "- Reproduce or verify the reported behavior before editing code.",
            "- Look for nearby tests or examples before implementing.",
            "- Keep the PR small and focused.",
            "- Mention validation evidence in the PR body.",
        ]
    )


def llm_prompt(score: IssueScore) -> str:
    issue = score.issue
    return f"""Create a concise pre-PR plan for this GitHub issue.

Issue: {issue.ref}
Title: {issue.title}
Labels: {', '.join(issue.labels) or 'none'}
Rule score: {score.total}
Rule type: {score.contribution_type}
Body:
{issue.body[:4000]}

Return Markdown with: summary, likely files to inspect, implementation path, tests, and whether to comment before coding.
"""


def generate_plan(score: IssueScore, config: LLMConfig | None = None) -> str:
    if config and has_llm_key(config):
        return chat_completion(config, llm_prompt(score))
    return rule_based_plan(score)
