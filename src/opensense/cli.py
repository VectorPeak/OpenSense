"""OpenSense command line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from opensense.config import OpenSenseConfig, initialize_state, load_config, validate_env_var_name
from opensense.core.daily import generate_daily_analysis
from opensense.core.planner import generate_plan
from opensense.core.ranking import rank_issues
from opensense.core.scoring import score_issue
from opensense.doctor import has_errors, run_checks
from opensense.github.client import GitHubClient
from opensense.github.issues import fetch_open_issues
from opensense.github.radar import fetch_radar
from opensense.llm.client import config_from_env
from opensense.storage.watchlist import add_repository, add_skill, load_repositories, load_skills, validate_repo_name


app = typer.Typer(help="Daily PR opportunity finder for known open-source repositories.")
watch_app = typer.Typer(help="Manage watched repositories and skills.")
watch_repo_app = typer.Typer(help="Manage watched repositories.")
watch_skill_app = typer.Typer(help="Manage watched skills.")
app.add_typer(watch_app, name="watch")
watch_app.add_typer(watch_repo_app, name="repo")
watch_app.add_typer(watch_skill_app, name="skill")
console = Console()

# Keep the product surface deliberately small. The CLI exposes five top-level
# verbs that map to the user's real contribution loop: initialize local state,
# maintain the watchlist, review daily candidates, evaluate one issue, and
# judge whether a repository is worth deeper PR effort.


def workspace_option() -> Optional[Path]:
    return typer.Option(None, "--workspace", help="Project workspace path. Defaults to current directory.")


@app.command()
def init(
    workspace: Optional[Path] = workspace_option(),
    github_token_env: str = typer.Option("GITHUB_TOKEN", help="Environment variable that stores the GitHub token."),
    llm_api_key_env: str = typer.Option("OPENSENSE_LLM_API_KEY", help="Environment variable that stores the LLM API key."),
    llm_base_url_env: str = typer.Option("OPENSENSE_LLM_BASE_URL", help="Environment variable that stores the LLM base URL."),
    llm_model_env: str = typer.Option("OPENSENSE_LLM_MODEL", help="Environment variable that stores the LLM model."),
    force: bool = typer.Option(False, "--force", help="Rewrite config and watchlist files."),
    check: bool = typer.Option(False, "--check", help="Run the same local health checks after initialization."),
) -> None:
    """Create local OpenSense state.

    `init --check` is also the home for local health checks, which preserves
    the five-command product surface while still giving users a way to verify
    config and environment variables.
    """

    try:
        config = OpenSenseConfig(
            github_token_env=validate_env_var_name(github_token_env, "--github-token-env"),
            llm_api_key_env=validate_env_var_name(llm_api_key_env, "--llm-api-key-env"),
            llm_base_url_env=validate_env_var_name(llm_base_url_env, "--llm-base-url-env"),
            llm_model_env=validate_env_var_name(llm_model_env, "--llm-model-env"),
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    root = initialize_state(workspace, config, force=force)
    typer.echo(f"Initialized OpenSense state at {root}")
    typer.echo("Secrets are read from environment variables; raw API keys are not stored.")
    if check:
        emit_checks(workspace)


@watch_repo_app.command("add")
def watch_repo_add(repo: str, workspace: Optional[Path] = workspace_option()) -> None:
    """Add an owner/repo entry to the watchlist."""

    try:
        added = add_repository(repo, workspace)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if added:
        typer.echo(f"Added {repo}")
    else:
        typer.echo(f"{repo} is already watched")


@watch_repo_app.command("list")
def watch_repo_list(workspace: Optional[Path] = workspace_option()) -> None:
    """List watched repositories."""

    try:
        repositories = load_repositories(workspace)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if not repositories:
        typer.echo("No watched repositories yet.")
        return
    for repo in repositories:
        typer.echo(repo)


@watch_skill_app.command("add")
def watch_skill_add(skill: str, workspace: Optional[Path] = workspace_option()) -> None:
    """Add a skill tag to the watchlist."""

    try:
        added = add_skill(skill, workspace)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    normalized = skill.strip().lower()
    if added:
        typer.echo(f"Added {normalized}")
    else:
        typer.echo(f"{normalized} is already watched")


@watch_skill_app.command("list")
def watch_skill_list(workspace: Optional[Path] = workspace_option()) -> None:
    """List watched skill tags."""

    try:
        skills = load_skills(workspace)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if not skills:
        typer.echo("No watched skills yet.")
        return
    for skill in skills:
        typer.echo(skill)


def emit_checks(workspace: Optional[Path]) -> None:
    """Print local health checks and exit non-zero when a hard error exists."""
    checks = run_checks(workspace)
    for check in checks:
        typer.echo(f"{check.status}: {check.name} - {check.detail}")
    if has_errors(checks):
        raise typer.Exit(1)


def parse_issue_ref(ref: str) -> tuple[str, int]:
    if "#" not in ref:
        raise typer.BadParameter("Issue must use owner/repo#number format.")
    repo_text, number_text = ref.rsplit("#", 1)
    try:
        repo = validate_repo_name(repo_text)
    except ValueError as exc:
        raise typer.BadParameter("Issue must use owner/repo#number format.") from exc
    try:
        number = int(number_text)
    except ValueError as exc:
        raise typer.BadParameter("Issue number must be an integer.") from exc
    if number <= 0:
        raise typer.BadParameter("Issue number must be greater than zero.")
    return repo, number


def github_client_for_workspace(workspace: Optional[Path]) -> GitHubClient:
    config = load_config(workspace)
    token_env = str(config.get("auth", {}).get("github_token_env", "GITHUB_TOKEN"))
    return GitHubClient(token_env=token_env)


def llm_config_for_workspace(workspace: Optional[Path], model: Optional[str] = None):
    config_data = load_config(workspace)
    llm = config_data.get("llm", {})
    llm_config = config_from_env(
        api_key_env=str(llm.get("api_key_env", "OPENSENSE_LLM_API_KEY")),
        base_url_env=str(llm.get("base_url_env", "OPENSENSE_LLM_BASE_URL")),
        model_env=str(llm.get("model_env", "OPENSENSE_LLM_MODEL")),
    )
    if model:
        llm_config = type(llm_config)(api_key_env=llm_config.api_key_env, base_url=llm_config.base_url, model=model)
    return llm_config


def find_open_issue(workspace: Optional[Path], issue_ref: str):
    """Fetch one issue by scanning recent open issues from its repository.

    This keeps the first MVP small: we reuse the same GitHub issue list endpoint
    as `daily` instead of adding another issue-specific endpoint and response
    shape. The trade-off is that very old open issues may not appear if they are
    outside the latest 100 open issues.
    """
    repo, number = parse_issue_ref(issue_ref)
    client = github_client_for_workspace(workspace)
    candidates = fetch_open_issues(client, repo, limit=100)
    match = next((item for item in candidates if item.number == number), None)
    if match is None:
        typer.echo(f"{issue_ref} was not found in the latest open issues.", err=True)
        raise typer.Exit(1)
    return match


@app.command()
def daily(
    workspace: Optional[Path] = workspace_option(),
    limit: int = typer.Option(10, "--limit", min=1, max=50, help="Maximum issues to show."),
    candidate_pool: int = typer.Option(30, "--candidate-pool", min=5, max=200, help="Maximum issues per repository to collect when --llm is enabled."),
    min_stars: int = typer.Option(0, "--min-stars", help="Minimum repository stars."),
    updated_days: int = typer.Option(30, "--updated-days", help="Prefer issues updated within this many days."),
    max_comments: int = typer.Option(20, "--max-comments", help="Maximum comments allowed for candidates."),
    llm: bool = typer.Option(False, "--llm", help="Use the configured LLM to find the best issues from a larger candidate pool."),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model name for --llm."),
) -> None:
    """Rank daily PR candidates from watched repositories."""

    try:
        repositories = load_repositories(workspace)
        skills = tuple(load_skills(workspace))
        client = github_client_for_workspace(workspace)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    issues = []
    fetch_limit = candidate_pool if llm else limit * 3
    for repo in repositories:
        issues.extend(fetch_open_issues(client, repo, limit=fetch_limit))
    llm_candidates = rank_issues(
        issues,
        limit=min(candidate_pool, 50),
        min_stars=min_stars,
        updated_days=updated_days,
        max_comments=max_comments,
        skills=skills,
    )
    ranked = rank_issues(
        issues,
        limit=limit,
        min_stars=min_stars,
        updated_days=updated_days,
        max_comments=max_comments,
        skills=skills,
    )

    table = Table(title="Daily PR candidates")
    table.add_column("#")
    table.add_column("Issue")
    table.add_column("Score")
    table.add_column("Type")
    table.add_column("Why")
    table.add_column("Next")
    for index, item in enumerate(ranked, start=1):
        table.add_row(
            str(index),
            item.issue.ref,
            str(item.total),
            item.contribution_type,
            "; ".join(item.reasons[:2]) or "rule match",
            f"opensense issue {item.issue.ref}",
        )
    console.print(table)
    if llm:
        try:
            console.print(
                Panel(
                    generate_daily_analysis(
                        llm_candidates,
                        skills,
                        llm_config_for_workspace(workspace, model),
                        display_limit=limit,
                    ),
                    title="LLM-Assisted Finding",
                )
            )
        except Exception as exc:
            typer.echo(f"LLM analysis failed: {exc}", err=True)
            raise typer.Exit(1) from exc


@app.command()
def issue(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    plan: bool = typer.Option(False, "--plan", help="Generate a PR plan after deterministic review."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Use rule-based planning even when an LLM key is available."),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model name for --plan."),
    min_stars: int = typer.Option(0, "--min-stars", help="Minimum repository stars."),
    updated_days: int = typer.Option(30, "--updated-days", help="Freshness window."),
    max_comments: int = typer.Option(20, "--max-comments", help="Comment risk threshold."),
) -> None:
    """Review one issue, optionally turning it into a PR plan.

    The default output is a deterministic review; `--plan` appends an
    LLM-assisted or rule-based PR plan. This matches the user's real flow after
    picking one daily candidate.
    """

    match = find_open_issue(workspace, issue)
    scored = score_issue(match, min_stars=min_stars, updated_days=updated_days, max_comments=max_comments)
    console.print(
        Panel(
            "\n".join(
                [
                    f"Score: {scored.total}",
                    f"Opportunity: {scored.opportunity}",
                    f"Smallness: {scored.smallness}",
                    f"Mergeability: {scored.mergeability}",
                    f"Type: {scored.contribution_type}",
                    "",
                    "Why:",
                    *(f"+ {reason}" for reason in scored.reasons),
                    "",
                    "Risk:",
                    *(f"- {risk}" for risk in scored.risks),
                ]
            ),
            title=match.ref,
        )
    )
    if plan:
        llm_config = None
        if not no_llm:
            llm_config = llm_config_for_workspace(workspace, model)
        console.print(generate_plan(scored, llm_config))


@app.command()
def repo(
    repos: list[str],
    workspace: Optional[Path] = workspace_option(),
    skills: str = typer.Option("", "--skills", help="Comma-separated skills/languages."),
    stale_days: int = typer.Option(30, "--stale-days", help="Open PRs older than this are stale."),
) -> None:
    """Evaluate whether repositories look worth a PR attempt.

    The command keeps repository-level merge and backlog signals behind a plain
    noun, which makes the command surface easier to remember beside `daily` and
    `issue`.
    """

    client = github_client_for_workspace(workspace)
    skill_items = tuple(item.strip() for item in skills.split(",") if item.strip())
    table = Table(title="Repository Signals")
    table.add_column("Repository")
    table.add_column("Score")
    table.add_column("Verdict")
    table.add_column("Signals")
    for repo in repos:
        result = fetch_radar(client, repo, skills=skill_items, stale_days=stale_days)
        table.add_row(
            result.repository,
            str(result.score),
            result.recommendation,
            "; ".join(result.reasons[:2] or result.risks[:2]),
        )
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
