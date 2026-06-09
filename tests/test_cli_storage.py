from pathlib import Path
from io import StringIO

import tomllib

from rich.console import Console
from typer.testing import CliRunner

from opensense.cli import app
from opensense.models import Issue, RadarResult


runner = CliRunner()


def read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


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


def test_watch_add_persists_repository_and_list_shows_it(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    add_result = runner.invoke(app, ["watch", "add", "fastapi/fastapi", "--workspace", str(tmp_path)])
    assert add_result.exit_code == 0, add_result.output

    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [{"name": "fastapi/fastapi"}]

    list_result = runner.invoke(app, ["watch", "list", "--workspace", str(tmp_path)])
    assert list_result.exit_code == 0, list_result.output
    assert "fastapi/fastapi" in list_result.output


def test_watch_add_rejects_invalid_repository_name(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    add_result = runner.invoke(app, ["watch", "add", "not-a-repo", "--workspace", str(tmp_path)])

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
    assert runner.invoke(app, ["watch", "add", "fastapi/fastapi", "--workspace", str(tmp_path)]).exit_code == 0

    second_init = runner.invoke(app, ["init", "--workspace", str(tmp_path)])

    assert second_init.exit_code == 0, second_init.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [{"name": "fastapi/fastapi"}]


def test_watch_add_does_not_duplicate_repository(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["watch", "add", "fastapi/fastapi", "--workspace", str(tmp_path)]).exit_code == 0

    duplicate = runner.invoke(app, ["watch", "add", "fastapi/fastapi", "--workspace", str(tmp_path)])

    assert duplicate.exit_code == 0, duplicate.output
    watchlist = read_toml(tmp_path / ".opensense" / "watchlist.toml")
    assert watchlist["repositories"] == [{"name": "fastapi/fastapi"}]


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


def test_help_exposes_only_five_top_level_product_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    registered_commands = {command.name or command.callback.__name__ for command in app.registered_commands}
    registered_groups = {group.name for group in app.registered_groups}

    assert registered_commands | registered_groups == {"init", "watch", "daily", "issue", "repo"}
    for retired_name in ("doctor", "inspect", "radar"):
        assert retired_name not in result.output


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

    monkeypatch.setattr("opensense.cli.load_watchlist", lambda workspace: ["owner/repo"])
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_open_issues", lambda client, repo, limit: [issue])
    output = StringIO()
    monkeypatch.setattr("opensense.cli.console", Console(file=output, width=180, color_system=None))

    result = runner.invoke(app, ["daily", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "opensense issue owner/repo#1" in output.getvalue()


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
