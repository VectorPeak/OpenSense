from pathlib import Path

import tomllib

from typer.testing import CliRunner

from opensense.cli import app


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


def test_doctor_warns_for_missing_optional_env_vars_after_init(tmp_path: Path) -> None:
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

    result = runner.invoke(app, ["doctor", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "OK: state directory" in result.output
    assert "WARN: GitHub token env" in result.output
    assert "WARN: LLM API key env" in result.output


def test_doctor_fails_before_init(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "ERROR: state directory" in result.output


def test_doctor_reports_invalid_config_toml(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", "--workspace", str(tmp_path)]).exit_code == 0
    (tmp_path / ".opensense" / "config.toml").write_text("[auth\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", "--workspace", str(tmp_path)])

    assert result.exit_code != 0
    assert "ERROR: config.toml - invalid TOML" in result.output
