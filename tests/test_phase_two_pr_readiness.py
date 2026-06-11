from pathlib import Path

import pytest
from typer.testing import CliRunner

from opensense.cli import app
from opensense.core.issue_ref import parse_issue_reference
from opensense.models import Issue
from opensense.storage.packs import pack_paths


runner = CliRunner()


def sample_issue() -> Issue:
    return Issue(
        owner="owner",
        repo="repo",
        number=7,
        title="Fix agent retrieval bug",
        body="The retriever returns stale results.",
        labels=("bug", "agent"),
        comments=2,
        repository_stars=1200,
        html_url="https://github.com/owner/repo/issues/7",
    )


def test_parse_issue_reference_accepts_url_and_short_ref() -> None:
    from_url = parse_issue_reference("https://github.com/owner/repo/issues/123")
    from_ref = parse_issue_reference("owner/repo#123")

    assert from_url == from_ref
    assert from_url.repository == "owner/repo"
    assert from_url.ref == "owner/repo#123"
    assert from_url.slug == "owner__repo/123"


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/owner/repo/pull/123",
        "https://example.com/owner/repo/issues/123",
        "owner/repo#0",
        "not-a-repo#1",
        "owner/repo#abc",
    ],
)
def test_parse_issue_reference_rejects_invalid_refs(value: str) -> None:
    with pytest.raises(ValueError):
        parse_issue_reference(value)


def test_pack_paths_are_stable(tmp_path: Path) -> None:
    issue_ref = parse_issue_reference("owner/repo#7")

    paths = pack_paths(issue_ref, tmp_path)

    assert paths.root == tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    assert paths.issue_md == paths.root / "issue.md"
    assert paths.agent_md == paths.root / "agent.md"
    assert paths.pr_summary_md == paths.root / "pr-summary.md"


def test_pack_writes_read_only_context_files(monkeypatch, tmp_path: Path) -> None:
    issue = sample_issue()
    source_file = tmp_path / "source.py"
    source_file.write_text("print('unchanged')\n", encoding="utf-8")
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)

    result = runner.invoke(app, ["pack", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    expected = {"issue.md", "repo.md", "files.md", "tests.md", "plan.md", "risks.md", "agent.md"}
    assert expected == {path.name for path in root.iterdir()}
    assert "Fix agent retrieval bug" in (root / "issue.md").read_text(encoding="utf-8")
    assert "untrusted user-supplied text" in (root / "issue.md").read_text(encoding="utf-8")
    assert "Do not open a PR, push, commit, or comment" in (root / "agent.md").read_text(encoding="utf-8")
    assert "Not run." in (root / "tests.md").read_text(encoding="utf-8")
    assert source_file.read_text(encoding="utf-8") == "print('unchanged')\n"


def test_pack_does_not_overwrite_without_force(monkeypatch, tmp_path: Path) -> None:
    issue = sample_issue()
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)
    first = runner.invoke(app, ["pack", "owner/repo#7", "--workspace", str(tmp_path)])
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["pack", "owner/repo#7", "--workspace", str(tmp_path)])

    assert second.exit_code == 1
    assert "--force" in second.output


def test_pack_refuses_secret_like_issue_body(monkeypatch, tmp_path: Path) -> None:
    issue = Issue(
        owner="owner",
        repo="repo",
        number=9,
        title="Fix leaked config",
        body="Here is a bad pasted key: sk-1234567890abcdefghijklmnop",
        labels=("bug",),
        repository_stars=1200,
    )
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)

    result = runner.invoke(app, ["pack", "owner/repo#9", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "Potential secret detected" in result.output
    assert "sk-1234567890abcdefghijklmnop" not in result.output
    assert not (tmp_path / ".opensense" / "packs" / "owner__repo" / "9" / "issue.md").exists()


def test_evidence_requires_existing_pack(tmp_path: Path) -> None:
    result = runner.invoke(app, ["evidence", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "Run `opensense pack <issue-url>` first" in result.output


def test_evidence_writes_drafts_from_existing_pack(monkeypatch, tmp_path: Path) -> None:
    issue = sample_issue()
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)
    assert runner.invoke(app, ["pack", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["evidence", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    assert (root / "pr-summary.md").exists()
    assert "Not run." in (root / "test-evidence.md").read_text(encoding="utf-8")
    assert "owner/repo#7" in (root / "maintainer-note.md").read_text(encoding="utf-8")


def test_patch_dry_run_does_not_modify_source(monkeypatch, tmp_path: Path) -> None:
    issue = sample_issue()
    source_file = tmp_path / "source.py"
    source_file.write_text("print('unchanged')\n", encoding="utf-8")
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)

    result = runner.invoke(app, ["patch", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Patch Dry Run" in result.output
    assert "no source files were modified" in result.output
    assert source_file.read_text(encoding="utf-8") == "print('unchanged')\n"


def test_patch_write_is_rejected(monkeypatch, tmp_path: Path) -> None:
    issue = sample_issue()
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)

    result = runner.invoke(app, ["patch", "owner/repo#7", "--write", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "source writes are not available" in result.output


def test_patch_dry_run_blocks_closed_issues(monkeypatch, tmp_path: Path) -> None:
    issue = Issue(
        owner="owner",
        repo="repo",
        number=11,
        title="Fix small agent bug",
        labels=("bug", "agent"),
        comments=1,
        repository_stars=1200,
        state="closed",
    )
    monkeypatch.setattr("opensense.cli.github_client_for_workspace", lambda workspace: object())
    monkeypatch.setattr("opensense.cli.fetch_issue", lambda client, repo, number: issue)

    result = runner.invoke(app, ["patch", "owner/repo#11", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Feasible for agent-assisted patch: no" in result.output
    assert "issue state is closed" in result.output
