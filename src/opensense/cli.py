"""OpenSense command line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from opensense.config import OpenSenseConfig, initialize_state, load_config, validate_env_var_name
from opensense.core.agent_workflow import generate_agent_apply, generate_agent_handoff, summarize_agent_status
from opensense.core.attempts import list_attempts, open_attempt
from opensense.core.daily import generate_daily_analysis
from opensense.core.evidence import generate_evidence
from opensense.core.issue_ref import parse_issue_reference
from opensense.core.pack import generate_pack
from opensense.core.patch import patch_dry_run
from opensense.core.planner import generate_plan
from opensense.core.pr_draft import generate_pr_draft
from opensense.core.proposal import generate_patch_proposal, normalize_language
from opensense.core.ranking import rank_issues
from opensense.core.sandbox import create_sandbox, load_sandbox
from opensense.core.scoring import score_issue
from opensense.core.test_capture import capture_test_run
from opensense.doctor import has_errors, run_checks
from opensense.github.client import GitHubClient, GitHubClientError
from opensense.github.issues import fetch_issue, fetch_open_issues
from opensense.github.radar import fetch_radar
from opensense.llm.client import config_from_env
from opensense.storage.watchlist import add_repository, add_skill, load_repositories, load_skills, validate_repo_name


app = typer.Typer(help="Daily PR opportunity finder for known open-source repositories.")
watch_app = typer.Typer(help="Manage watched repositories and skills.")
watch_repo_app = typer.Typer(help="Manage watched repositories.")
watch_skill_app = typer.Typer(help="Manage watched skills.")
sandbox_app = typer.Typer(help="Manage isolated local worktrees for issue attempts.")
test_app = typer.Typer(help="Capture local test evidence for issue attempts.")
pr_app = typer.Typer(help="Generate local pull request drafts.")
agent_app = typer.Typer(help="Prepare and run controlled coding-agent attempts.")
attempt_app = typer.Typer(help="Inspect local PR attempt artifacts.")
app.add_typer(watch_app, name="watch")
watch_app.add_typer(watch_repo_app, name="repo")
watch_app.add_typer(watch_skill_app, name="skill")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(test_app, name="test")
app.add_typer(pr_app, name="pr")
app.add_typer(agent_app, name="agent")
app.add_typer(attempt_app, name="attempt")
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
    try:
        issue_ref = parse_issue_reference(ref)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return issue_ref.repository, issue_ref.number


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
    """Fetch one issue directly by reference."""

    repo, number = parse_issue_ref(issue_ref)
    client = github_client_for_workspace(workspace)
    try:
        issue = fetch_issue(client, repo, number)
    except (GitHubClientError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if issue.state.lower() != "open":
        typer.echo(f"{issue.ref} is {issue.state}; OpenSense issue review only accepts open issues.", err=True)
        raise typer.Exit(1)
    return issue


def fetch_one_issue(workspace: Optional[Path], issue_text: str):
    try:
        issue_ref = parse_issue_reference(issue_text)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    client = github_client_for_workspace(workspace)
    try:
        issue = fetch_issue(client, issue_ref.repository, issue_ref.number)
    except (GitHubClientError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    return issue_ref, issue


@app.command()
def daily(
    workspace: Optional[Path] = workspace_option(),
    limit: int = typer.Option(10, "--limit", min=1, max=50, help="Maximum issues to show."),
    candidate_pool: int = typer.Option(30, "--candidate-pool", min=5, max=200, help="Maximum issues per repository to collect for LLM-assisted finding."),
    min_stars: int = typer.Option(0, "--min-stars", help="Minimum repository stars."),
    updated_days: int = typer.Option(30, "--updated-days", help="Prefer issues updated within this many days."),
    max_comments: int = typer.Option(20, "--max-comments", help="Maximum comments allowed for candidates."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM-assisted finding and only use rule-based ranking."),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model name for daily LLM analysis."),
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
    use_llm = not no_llm
    fetch_limit = candidate_pool if use_llm else limit * 3
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
    if use_llm:
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
def pack(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite existing pack files."),
    language: str = typer.Option("en", "--language", help="Output language for generated markdown: en or zh."),
) -> None:
    """Generate a read-only context pack for one issue."""

    issue_ref, fetched_issue = fetch_one_issue(workspace, issue)
    try:
        result = generate_pack(fetched_issue, issue_ref, workspace, force=force, language=normalize_language(language))
    except (FileExistsError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Context pack written to {result.root}")
    for path in result.written_files:
        console.print(f"- {path.relative_to(result.root)}")


@app.command()
def evidence(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite existing evidence files."),
) -> None:
    """Generate PR evidence drafts from an existing context pack."""

    try:
        issue_ref = parse_issue_reference(issue)
        result = generate_evidence(issue_ref, workspace, force=force)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Evidence files written to {result.root}")
    for path in result.written_files:
        console.print(f"- {path.name}")


@app.command()
def patch(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    dry_run: bool = typer.Option(True, "--dry-run/--write", help="Only --dry-run is supported in phase two."),
) -> None:
    """Evaluate whether one issue is suitable for agent-assisted patch work."""

    if not dry_run:
        typer.echo("Phase two only supports `opensense patch <issue> --dry-run`; source writes are not available.", err=True)
        raise typer.Exit(1)
    issue_ref, fetched_issue = fetch_one_issue(workspace, issue)
    result = patch_dry_run(fetched_issue)
    console.print(
        Panel(
            "\n".join(
                [
                    f"Issue: {issue_ref.ref}",
                    f"Feasible for agent-assisted patch: {'yes' if result.feasible else 'no'}",
                    f"Confidence: {result.confidence}",
                    "",
                    "Risks:",
                    *(f"- {risk}" for risk in result.risks),
                    "",
                    "Required context:",
                    *(f"- {item}" for item in result.required_context),
                    "",
                    "Suggested dry-run steps:",
                    *(f"- {item}" for item in result.suggested_steps),
                    "",
                    "Safety: no source files were modified, no branch was created, and no PR was opened.",
                ]
            ),
            title="Patch Dry Run",
        )
    )


@app.command("propose")
def propose(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing patch-proposal.md."),
    language: Optional[str] = typer.Option(None, "--language", help="Output language for patch-proposal.md: en or zh. Defaults to the pack language."),
) -> None:
    """Write a patch proposal from an existing validated context pack."""

    try:
        issue_ref = parse_issue_reference(issue)
        path = generate_patch_proposal(issue_ref, workspace, force=force, language=language)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Patch proposal written to {path}")


@sandbox_app.command("create")
def sandbox_create(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    allow_dirty: bool = typer.Option(False, "--allow-dirty", help="Allow creating a sandbox from a dirty workspace and record the dirty snapshot."),
) -> None:
    """Create an isolated git worktree for one issue."""

    try:
        issue_ref = parse_issue_reference(issue)
        info = create_sandbox(issue_ref, workspace, allow_dirty=allow_dirty)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Sandbox created at {info.worktree_path}")
    console.print(f"Branch: {info.branch_name}")


@sandbox_app.command("status")
def sandbox_status(issue: str, workspace: Optional[Path] = workspace_option()) -> None:
    """Show sandbox metadata for one issue."""

    try:
        issue_ref = parse_issue_reference(issue)
        info = load_sandbox(issue_ref, workspace)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    table = Table(title=f"Sandbox {info.issue_ref}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("branch", info.branch_name)
    table.add_row("worktree", info.worktree_path)
    table.add_row("base_commit", info.base_commit or "unknown")
    table.add_row("dirty_policy", info.dirty_policy)
    table.add_row("safety_status", info.safety_status)
    console.print(table)


@agent_app.command("handoff")
def agent_handoff(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing agent handoff."),
) -> None:
    """Write a local task brief for an external coding agent."""

    try:
        issue_ref = parse_issue_reference(issue)
        result = generate_agent_handoff(issue_ref, workspace, force=force)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Agent handoff written to {result.root}")
    for path in result.written_files:
        console.print(f"- {path.name}")


@agent_app.command("apply", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def agent_apply(
    ctx: typer.Context,
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite existing agent apply artifacts."),
    timeout: int = typer.Option(1800, "--timeout", min=1, help="Maximum command runtime in seconds."),
) -> None:
    """Run one explicit agent command inside the issue sandbox and capture diff evidence."""

    try:
        issue_ref = parse_issue_reference(issue)
        result = generate_agent_apply(issue_ref, tuple(ctx.args), workspace, force=force, timeout=timeout)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Agent apply artifacts written to {result.root}")
    for path in result.written_files:
        console.print(f"- {path.name}")
    console.print(f"Status: {result.status}")
    if result.status != "passed":
        raise typer.Exit(1)


@agent_app.command("status")
def agent_status(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Show the local PR-attempt state for one issue."""

    try:
        issue_ref = parse_issue_reference(issue)
        result = summarize_agent_status(issue_ref, workspace)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if as_json:
        typer.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    table = Table(title=f"OpenSense attempt status: {result.issue_ref}")
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Detail")
    for step, status, detail in result.rows:
        table.add_row(step, status, detail)
    console.print(table)
    console.print(f"Next: {result.next_step}")


@attempt_app.command("list")
def attempt_list(
    workspace: Optional[Path] = workspace_option(),
    limit: int = typer.Option(20, "--limit", min=1, max=100, help="Maximum attempts to show."),
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """List local issue attempts under .opensense/packs."""

    attempts = list_attempts(workspace, limit=limit)
    if as_json:
        typer.echo(json.dumps({"attempts": [item.to_dict() for item in attempts]}, indent=2, ensure_ascii=False))
        return
    table = Table(title="OpenSense attempts")
    table.add_column("Issue")
    table.add_column("Status")
    table.add_column("Next")
    table.add_column("Root")
    for item in attempts:
        table.add_row(item.issue_ref, item.status, item.next_step, str(item.root))
    console.print(table)


@attempt_app.command("open")
def attempt_open(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Show local paths for one issue attempt."""

    try:
        result = open_attempt(issue, workspace)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if as_json:
        typer.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    console.print(f"Attempt root: {result.root}")
    if result.pr_draft:
        console.print(f"PR draft: {result.pr_draft}")
    if result.agent_handoff:
        console.print(f"Agent handoff: {result.agent_handoff}")
    if result.diffstat:
        console.print(f"Diffstat: {result.diffstat}")


@test_app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def test_run(
    ctx: typer.Context,
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite existing test evidence files."),
    timeout: int = typer.Option(600, "--timeout", min=1, help="Maximum command runtime in seconds."),
) -> None:
    """Run one explicit local test command and capture auditable evidence."""

    try:
        issue_ref = parse_issue_reference(issue)
        result = capture_test_run(issue_ref, tuple(ctx.args), workspace, force=force, timeout=timeout)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"Test evidence written to {result.root}")
    for path in result.written_files:
        console.print(f"- {path.name}")
    console.print(f"Status: {result.status}")
    if result.status != "passed":
        raise typer.Exit(1)


@pr_app.command("draft")
def pr_draft(
    issue: str,
    workspace: Optional[Path] = workspace_option(),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing PR draft."),
) -> None:
    """Generate a local PR title/body draft from pack and test evidence."""

    try:
        issue_ref = parse_issue_reference(issue)
        result = generate_pr_draft(issue_ref, workspace, force=force)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except (FileExistsError, FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    console.print(f"PR draft written to {result.root}")
    for path in result.written_files:
        console.print(f"- {path.name}")


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
