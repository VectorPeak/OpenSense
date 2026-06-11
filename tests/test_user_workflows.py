from io import StringIO
from pathlib import Path

import tomllib
from rich.console import Console
from typer.testing import CliRunner

from opensense.cli import app
from opensense.config import DEFAULT_REPOSITORIES, DEFAULT_SKILLS
from opensense.models import Issue


runner = CliRunner()


def read_watchlist(workspace: Path) -> dict:
    path = workspace / ".opensense" / "watchlist.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_new_agent_rag_user_can_initialize_and_extend_watchlist(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    add_repo = runner.invoke(
        app,
        ["watch", "repo", "add", "QwenLM/qwen-code", "--workspace", str(tmp_path)],
    )
    add_skill = runner.invoke(
        app,
        ["watch", "skill", "add", "python", "--workspace", str(tmp_path)],
    )

    watchlist = read_watchlist(tmp_path)
    repositories = [item["name"] for item in watchlist["repositories"]]

    assert init_result.exit_code == 0, init_result.output
    assert add_repo.exit_code == 0, add_repo.output
    assert add_skill.exit_code == 0, add_skill.output
    assert repositories == [*DEFAULT_REPOSITORIES, "QwenLM/qwen-code"]
    assert watchlist["skills"] == [*DEFAULT_SKILLS, "python"]


def test_force_init_restores_curated_agent_rag_defaults(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(
        app,
        ["watch", "repo", "add", "QwenLM/qwen-code", "--workspace", str(tmp_path)],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["watch", "skill", "add", "python", "--workspace", str(tmp_path)],
    ).exit_code == 0

    force_result = runner.invoke(app, ["init", "--force", "--workspace", str(tmp_path)])
    watchlist = read_watchlist(tmp_path)

    assert force_result.exit_code == 0, force_result.output
    assert [item["name"] for item in watchlist["repositories"]] == list(DEFAULT_REPOSITORIES)
    assert watchlist["skills"] == list(DEFAULT_SKILLS)


def test_daily_uses_default_skills_to_prioritize_agent_rag_issue(monkeypatch, tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    agent_issue = Issue(
        owner="openclaw",
        repo="openclaw",
        number=101,
        title="Fix agent memory retrieval failure",
        labels=("bug", "rag"),
        comments=1,
        repository_stars=1000,
    )
    generic_issue = Issue(
        owner="vllm-project",
        repo="vllm",
        number=202,
        title="Fix generic runtime failure",
        labels=("bug",),
        comments=1,
        repository_stars=1000,
    )

    def fake_fetch_open_issues(client, repo: str, limit: int) -> list[Issue]:
        if repo == "openclaw/openclaw":
            return [agent_issue]
        if repo == "vllm-project/vllm":
            return [generic_issue]
        return []

    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", fake_fetch_open_issues)
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--workspace", str(tmp_path)])
    text = output.getvalue()

    assert result.exit_code == 0, result.output
    assert text.index("openclaw/openclaw#101") < text.index("vllm-project/vllm#202")
    assert "matches watched skill: agent, rag" in text
