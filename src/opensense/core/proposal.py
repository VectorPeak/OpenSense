"""Patch proposal generation from a validated context pack."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from opensense.core.issue_ref import IssueRef
from opensense.storage.packs import ensure_pack_can_write, pack_paths, require_valid_pack


OutputLanguage = Literal["en", "zh"]


def proposal_markdown(pack: dict, language: OutputLanguage = "en") -> str:
    issue = pack.get("issue", {})
    facts = pack.get("facts", {})
    inferences = pack.get("inferences", {})
    risks = pack.get("risks", [])
    unknowns = pack.get("unknowns", [])
    test_guidance = pack.get("test_guidance", {})
    constraints = pack.get("agent_constraints", [])
    searches = inferences.get("candidate_file_searches", [])
    commands = test_guidance.get("suggested_commands", [])
    if language == "zh":
        return "\n".join(
            [
                "# Patch Proposal",
                "",
                f"Issue: {issue.get('ref', 'unknown')}",
                f"标题: {issue.get('title', 'unknown')}",
                f"贡献类型: {inferences.get('contribution_type', 'unknown')}",
                f"分数: {inferences.get('score', 'unknown')}",
                f"仓库: {facts.get('repository', 'unknown')}",
                "",
                "## 优先检查的文件",
                *(f"- {item}" for item in searches),
                *(["- 目前还不知道具体目标文件；请先阅读 issue 并在本地搜索。"] if not searches else []),
                "",
                "## 最小改动方向",
                "- 改代码前先复现或验证报告的问题。",
                "- 只做能解决当前 issue 的最小改动。",
                "- 优先补充或更新一个聚焦的回归测试。",
                "",
                "## 建议运行的测试",
                *(f"- {item}" for item in commands),
                *(["- 暂时未知。编码前先阅读仓库测试说明。"] if not commands else []),
                "",
                "## 停止条件",
                "- 如果 issue 已被认领或已有活跃 PR 覆盖，停止。",
                "- 如果改动涉及认证、安全、隐私、支付、许可证或法律逻辑，停止。",
                "- 如果预期改动超过五个文件或大约 300 行，停止。",
                "- 如果找不到复现或验证路径，停止。",
                "",
                "## 风险",
                *(f"- {item}" for item in risks),
                *(["- pack.json 中没有记录规则风险。"] if not risks else []),
                "",
                "## 未知项",
                *(f"- {item}" for item in unknowns),
                "",
                "## Agent 约束",
                *(f"- {item}" for item in constraints),
                "",
                "## PR 证据要求",
                "- 真实测试命令和退出码。",
                "- 简洁说明为什么这个 patch 能解决问题。",
                "- 清楚写出限制，以及哪些内容尚未验证。",
            ]
        )
    return "\n".join(
        [
            "# Patch Proposal",
            "",
            f"Issue: {issue.get('ref', 'unknown')}",
            f"Title: {issue.get('title', 'unknown')}",
            f"Contribution type: {inferences.get('contribution_type', 'unknown')}",
            f"Score: {inferences.get('score', 'unknown')}",
            f"Repository: {facts.get('repository', 'unknown')}",
            "",
            "## Target Files To Inspect",
            *(f"- {item}" for item in searches),
            *(["- No target file is known yet; inspect the issue and search locally first."] if not searches else []),
            "",
            "## Likely Smallest Change",
            "- Reproduce or verify the reported behavior before editing.",
            "- Make the narrowest change that addresses this issue only.",
            "- Prefer adding or updating a focused regression test.",
            "",
            "## Tests To Run",
            *(f"- {item}" for item in commands),
            *(["- Not known yet. Read repository test instructions before coding."] if not commands else []),
            "",
            "## Stop Conditions",
            "- Stop if the issue is already assigned or covered by an active PR.",
            "- Stop if the change touches auth, security, privacy, payment, license, or legal logic.",
            "- Stop if the expected change grows beyond five files or roughly 300 changed lines.",
            "- Stop if no reproduction or verification path can be found.",
            "",
            "## Risks",
            *(f"- {item}" for item in risks),
            *(["- No rule-based risk was recorded in pack.json."] if not risks else []),
            "",
            "## Unknowns",
            *(f"- {item}" for item in unknowns),
            "",
            "## Agent Constraints",
            *(f"- {item}" for item in constraints),
            "",
            "## PR Evidence Required",
            "- Real test commands and exit codes.",
            "- A concise explanation of why the patch fixes the issue.",
            "- Clear limitations and anything not verified.",
        ]
    )


def normalize_language(language: str | None) -> OutputLanguage:
    value = (language or "en").strip().lower()
    if value not in {"en", "zh"}:
        raise ValueError("Language must be one of: en, zh.")
    return value  # type: ignore[return-value]


def generate_patch_proposal(issue_ref: IssueRef, workspace: Path | None = None, *, force: bool = False, language: str | None = None) -> Path:
    paths = pack_paths(issue_ref, workspace)
    payload = require_valid_pack(paths, issue_ref.ref)
    selected_language = normalize_language(language or str(payload["manifest"].get("language") or "en"))
    ensure_pack_can_write(paths, ("patch-proposal.md",), force=force)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.patch_proposal_md.parent.mkdir(parents=True, exist_ok=True)
    paths.patch_proposal_md.write_text(proposal_markdown(payload["pack"], selected_language).rstrip() + "\n", encoding="utf-8", newline="\n")
    return paths.patch_proposal_md
