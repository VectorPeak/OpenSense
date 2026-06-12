from pathlib import Path
from io import StringIO

import tomllib

from rich.console import Console
from typer.testing import CliRunner

from opensense.cli import app
from opensense.config import DEFAULT_REPOSITORIES, DEFAULT_SKILLS
from opensense.models import Issue, RadarResult


runner = CliRunner()


def read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def default_repository_tables() -> list[dict[str, str]]:
    return [{"name": repo} for repo in DEFAULT_REPOSITORIES]


def test_init_creates_local_state_without_storing_raw_api_key(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--workspace",
            str(tmp_path),
            "--github-token-env",
            "GH_TOKEN",
            "--llm-api-key-env",
            "OPENAI_API_KEY",
        ],
    )

    assert result.exit_code == 0, result.output
    state_dir = tmp_path / ".opensense"
    assert (state_dir / "cache").is_dir()
    assert (state_dir / "reports").is_dir()

    config = read_toml(state_dir / "config.toml")
    assert config["auth"]["github_token_env"] == "GH_TOKEN"
    assert config["auth"]["llm_api_key_env"] == "OPENAI_API_KEY"
    assert "sk-" not in str(config).lower()
    assert "github_pat_" not in str(config).lower()
    watchlist = read_toml(state_dir / "watchlist.toml")
    assert watchlist["repositories"] == default_repository_tables()
    assert watchlist["skills"] == list(DEFAULT_SKILLS)


def test_watch_repo_add_persists_repository_and_list_shows_it(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    add_result = runner.invoke(app, ["watch", "repo", "add", "fastapi/fastapi", "--workspace", str(tmp_path)])
    assert add_result.exit_code == 0, add_result.output

    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [*default_repository_tables(), {"name": "fastapi/fastapi"}]

    list_result = runner.invoke(app, ["watch", "repo", "list", "--workspace", str(tmp_path)])
    assert list_result.exit_code == 0, list_result.output
    assert "fastapi/fastapi" in list_result.output


def test_watch_repo_add_rejects_invalid_repository_name(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    add_result = runner.invoke(app, ["watch", "repo", "add", "not-a-repo", "--workspace", str(tmp_path)])

    assert add_result.exit_code != 0
    assert "owner/repo" in add_result.output


def test_init_rejects_raw_secret_values_for_env_var_options(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--workspace",
            str(tmp_path),
            "--llm-api-key-env",
            "sk-test-secret",
        ],
    )

    assert result.exit_code != 0
    assert "environment variable name" in result.output
    assert not (tmp_path / ".opensense" / "config.toml").exists()


def test_init_is_idempotent_and_keeps_watchlist(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "repo", "add", "fastapi/fastapi", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "skill", "add", "Python", "--workspace", str(tmp_path)]).exit_code == 0

    second_init = runner.invoke(app, ["init", "--workspace", str(tmp_path)])

    assert second_init.exit_code == 0, second_init.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [*default_repository_tables(), {"name": "fastapi/fastapi"}]
    assert watchlist["skills"] == [*DEFAULT_SKILLS, "python"]


def test_watch_repo_add_does_not_duplicate_repository(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "repo", "add", "fastapi/fastapi", "--workspace", str(tmp_path)]).exit_code == 0

    duplicate = runner.invoke(app, ["watch", "repo", "add", "fastapi/fastapi", "--workspace", str(tmp_path)])

    assert duplicate.exit_code == 0, duplicate.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [*default_repository_tables(), {"name": "fastapi/fastapi"}]


def test_watch_skill_add_persists_skill_and_list_shows_it(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0

    add_python = runner.invoke(app, ["watch", "skill", "add", "Python", "--workspace", str(tmp_path)])
    add_llm = runner.invoke(app, ["watch", "skill", "add", "llm", "--workspace", str(tmp_path)])

    assert add_python.exit_code == 0, add_python.output
    assert add_llm.exit_code == 0, add_llm.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["skills"] == [*DEFAULT_SKILLS, "python", "llm"]

    list_result = runner.invoke(app, ["watch", "skill", "list", "--workspace", str(tmp_path)])
    assert list_result.exit_code == 0, list_result.output
    assert "python" in list_result.output
    assert "llm" in list_result.output


def test_watch_repo_and_skill_do_not_overwrite_each_other(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "repo", "add", "fastapi/fastapi", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "skill", "add", "python", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "repo", "add", "encode/httpx", "--workspace", str(tmp_path)]).exit_code == 0

    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [
        *default_repository_tables(),
        {"name": "fastapi/fastapi"},
        {"name": "encode/httpx"},
    ]
    assert watchlist["skills"] == [*DEFAULT_SKILLS, "python"]


def test_watch_skill_add_does_not_duplicate_case_insensitive_skill(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "skill", "add", "Python", "--workspace", str(tmp_path)]).exit_code == 0

    duplicate = runner.invoke(app, ["watch", "skill", "add", "python", "--workspace", str(tmp_path)])

    assert duplicate.exit_code == 0, duplicate.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["skills"] == [*DEFAULT_SKILLS, "python"]


def test_watch_skill_add_rejects_invalid_skill(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["watch", "skill", "add", "python,llm", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "Skill must be a single tag" in result.output


def test_watch_repo_and_skill_fail_before_init(tmp_path: Path) -> None:
    commands = [
        ["watch", "repo", "add", "fastapi/fastapi"],
        ["watch", "repo", "list"],
        ["watch", "skill", "add", "python"],
        ["watch", "skill", "list"],
    ]

    for command in commands:
        result = runner.invoke(app, [*command, "--workspace", str(tmp_path)])
        assert result.exit_code != 0
        assert "opensense init" in result.output


def test_old_watch_add_and_list_are_not_available() -> None:
    for command in (["watch", "add", "fastapi/fastapi"], ["watch", "list"]):
        result = runner.invoke(app, command)
        assert result.exit_code != 0


def test_init_force_restores_default_repositories_and_skills(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "repo", "add", "fastapi/fastapi", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "skill", "add", "python", "--workspace", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["init", "--workspace", str(tmp_path), "--force"])

    assert result.exit_code == 0, result.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == default_repository_tables()
    assert watchlist["skills"] == list(DEFAULT_SKILLS)


def test_init_check_warns_for_missing_optional_env_vars_after_init(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--workspace",
            str(tmp_path),
            "--github-token-env",
            "OPENSENSE_TEST_MISSING_GITHUB_TOKEN",
            "--llm-api-key-env",
            "OPENSENSE_TEST_MISSING_LLM_KEY",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["init", "--workspace", str(tmp_path), "--check"])

    assert result.exit_code == 0, result.output
    assert "OK: state directory" in result.output
    assert "WARN: GitHub token env" in result.output
    assert "WARN: LLM API key env" in result.output


def test_init_check_creates_state_and_reports_health(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--workspace", str(tmp_path), "--check"])

    assert result.exit_code == 0
    assert "OK: state directory" in result.output


def test_init_check_reports_invalid_config_toml(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    (tmp_path / ".opensense" / "config.toml").write_text("[auth\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--workspace", str(tmp_path), "--check"])

    assert result.exit_code != 0
    assert "ERROR: config.toml - invalid TOML" in result.output


def test_help_exposes_current_top_level_product_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    registered_commands = {command.name or command.callback.__name__ for command in app.registered_commands}
    registered_groups = {group.name for group in app.registered_groups}

    assert registered_commands | registered_groups == {
        "init",
        "watch",
        "daily",
        "issue",
        "repo",
        "pack",
        "evidence",
        "patch",
        "propose",
        "sandbox",
        "test",
        "pr",
    }
    for retired_name in ("doctor", "inspect", "radar"):
        assert retired_name not in result.output


def test_watch_help_exposes_repo_and_skill_groups_only() -> None:
    result = runner.invoke(app, ["watch", "--help"])

    assert result.exit_code == 0, result.output
    assert "repo" in result.output
    assert "skill" in result.output
    assert " add " not in result.output
    assert " list " not in result.output


def test_merged_top_level_commands_are_no_longer_available() -> None:
    for command in ("doctor", "inspect", "plan", "radar"):
        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code != 0


def test_daily_points_next_step_to_issue_command(monkeypatch, tmp_path: Path) -> None:
    issue = Issue(
        owner="owner",
        repo="repo",
        number=1,
        title="Fix flaky CLI test",
        labels=("bug", "good first issue"),
        comments=1,
        repository_stars=900,
    )

    monkeypatch.setattr("opensense.cli.load_repositories", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.load_skills", lambda workspace: [])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [issue])
    monkeypatch.setattr("opensense.cli.llm_config_for_workspace", lambda workspace, model=None: None)
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "opensense issue owner/repo#1" in output.getvalue()


def test_daily_uses_watched_skills_to_boost_matching_issues(monkeypatch, tmp_path: Path) -> None:
    python_issue = Issue(
        owner="owner",
        repo="repo",
        number=1,
        title="Fix Python CLI crash",
        labels=("bug",),
        comments=1,
        repository_stars=900,
    )
    generic_issue = Issue(
        owner="owner",
        repo="repo",
        number=2,
        title="Fix generic CLI crash",
        labels=("bug",),
        comments=1,
        repository_stars=900,
    )

    monkeypatch.setattr("opensense.cli.load_repositories", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.load_skills", lambda workspace: ["python"])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [generic_issue, python_issue])
    monkeypatch.setattr("opensense.cli.llm_config_for_workspace", lambda workspace, model=None: None)
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--workspace", str(tmp_path)])

    text = output.getvalue()
    assert result.exit_code == 0, result.output
    assert text.index("owner/repo#1") < text.index("owner/repo#2")
    assert "matches watched skill: python" in text


def test_daily_prints_llm_finding_by_default(monkeypatch, tmp_path: Path) -> None:
    fetch_limits: list[int] = []
    issue = Issue(
        owner="owner",
        repo="repo",
        number=3,
        title="Fix agent retrieval bug",
        labels=("bug", "agent"),
        comments=1,
        repository_stars=900,
    )

    monkeypatch.setattr("opensense.cli.load_repositories", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.load_skills", lambda workspace: ["agent"])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr(
        "opensense.cli.fetch_open_issues",
        lambda client, repo, limit: fetch_limits.append(limit) or [issue],
    )
    monkeypatch.setattr("opensense.cli.llm_config_for_workspace", lambda workspace, model=None: object())
    monkeypatch.setattr(
        "opensense.cli.generate_daily_analysis",
        lambda ranked, skills, config, display_limit=10: "Pick owner/repo#3 first.",
    )
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--workspace", str(tmp_path)])

    text = output.getvalue()
    assert result.exit_code == 0, result.output
    assert fetch_limits == [30]
    assert "LLM-Assisted Finding" in text
    assert "Pick owner/repo#3 first." in text


def test_daily_no_llm_uses_smaller_rule_based_fetch(monkeypatch, tmp_path: Path) -> None:
    fetch_limits: list[int] = []
    issue = Issue(
        owner="owner",
        repo="repo",
        number=31,
        title="Fix test crash",
        labels=("bug",),
        comments=1,
        repository_stars=900,
    )

    monkeypatch.setattr("opensense.cli.load_repositories", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.load_skills", lambda workspace: [])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr(
        "opensense.cli.fetch_open_issues",
        lambda client, repo, limit: fetch_limits.append(limit) or [issue],
    )
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--no-llm", "--limit", "5", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert fetch_limits == [15]
    assert "LLM-Assisted Finding" not in output.getvalue()


def test_daily_llm_candidate_pool_controls_fetch_size(monkeypatch, tmp_path: Path) -> None:
    fetch_limits: list[int] = []
    issue = Issue(
        owner="owner",
        repo="repo",
        number=33,
        title="Fix RAG agent state",
        labels=("bug", "rag"),
        comments=1,
        repository_stars=900,
    )

    monkeypatch.setattr("opensense.cli.load_repositories", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.load_skills", lambda workspace: ["rag"])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr(
        "opensense.cli.fetch_open_issues",
        lambda client, repo, limit: fetch_limits.append(limit) or [issue],
    )
    monkeypatch.setattr("opensense.cli.llm_config_for_workspace", lambda workspace, model=None: object())
    monkeypatch.setattr(
        "opensense.cli.generate_daily_analysis",
        lambda ranked, skills, config, display_limit=10: f"pool={len(ranked)} limit={display_limit}",
    )
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--candidate-pool", "42", "--limit", "5", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert fetch_limits == [42]
    assert "pool=1 limit=5" in output.getvalue()


def test_daily_llm_reports_failure_without_traceback(monkeypatch, tmp_path: Path) -> None:
    issue = Issue(
        owner="owner",
        repo="repo",
        number=4,
        title="Fix RAG indexing bug",
        labels=("bug", "rag"),
        comments=1,
        repository_stars=900,
    )

    monkeypatch.setattr("opensense.cli.load_repositories", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.load_skills", lambda workspace: ["rag"])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [issue])
    monkeypatch.setattr("opensense.cli.llm_config_for_workspace", lambda workspace, model=None: object())

    def fail_analysis(ranked, skills, config, display_limit=10):
        raise RuntimeError("provider rejected request")

    monkeypatch.setattr("opensense.cli.generate_daily_analysis", fail_analysis)

    result = runner.invoke(app, ["daily", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "LLM analysis failed: provider rejected request" in result.output
    assert "Traceback" not in result.output


def test_issue_inspects_one_candidate(monkeypatch, tmp_path: Path) -> None:
    issue = Issue(
        owner="owner",
        repo="repo",
        number=7,
        title="Add missing parser test",
        labels=("test",),
        comments=0,
        repository_stars=1200,
    )

    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [issue])

    result = runner.invoke(app, ["issue", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "owner/repo#7" in result.output
    assert "Score:" in result.output


def test_issue_plan_can_run_without_llm(monkeypatch, tmp_path: Path) -> None:
    issue = Issue(
        owner="owner",
        repo="repo",
        number=8,
        title="Fix crash on empty config",
        labels=("bug",),
        comments=2,
        repository_stars=1200,
    )

    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [issue])

    result = runner.invoke(app, ["issue", "owner/repo#8", "--plan", "--no-llm", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "# PR Plan for owner/repo#8" in result.output


def test_issue_rejects_invalid_reference(tmp_path: Path) -> None:
    result = runner.invoke(app, ["issue", "not-a-reference", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "owner/repo#number" in result.output


def test_issue_rejects_malformed_repository_reference(tmp_path: Path) -> None:
    result = runner.invoke(app, ["issue", "not-a-repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "owner/repo#number" in result.output


def test_issue_rejects_non_positive_issue_number(tmp_path: Path) -> None:
    result = runner.invoke(app, ["issue", "owner/repo#0", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "greater than zero" in result.output


def test_issue_reports_when_recent_open_issue_is_not_found(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [])

    result = runner.invoke(app, ["issue", "owner/repo#99", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "was not found in the latest open issues" in result.output


def test_repo_splits_skills_and_displays_radar(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, tuple[str, ...]] = {}

    def fake_fetch_radar(client, repo: str, *, skills: tuple[str, ...], stale_days: int) -> RadarResult:
        captured["skills"] = skills
        return RadarResult(
            repository=repo,
            score=82,
            recommendation="Go",
            reasons=("language matches your skills",),
        )

    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_radar", fake_fetch_radar)

    result = runner.invoke(app, ["repo", "owner/repo", "--skills", "python,llm", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Repository Signals" in result.output
    assert "owner/repo" in result.output
    assert captured["skills"] == ("python", "llm")
