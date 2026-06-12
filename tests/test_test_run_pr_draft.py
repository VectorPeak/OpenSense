import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from opensense.cli import app
from opensense.core.issue_ref import parse_issue_reference
from opensense.storage.packs import PACK_FILENAMES, pack_paths


runner = CliRunner()


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)


def init_git_repo(path: Path) -> None:
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test User")
    (path / ".gitignore").write_text(".opensense/\n", encoding="utf-8")
    (path / "README.md").write_text("# Demo\n", encoding="utf-8")
    git(path, "add", ".gitignore", "README.md")
    result = git(path, "commit", "-m", "init")
    assert result.returncode == 0, result.stderr


def write_valid_pack(workspace: Path, issue_text: str = "owner/repo#7") -> None:
    issue_ref = parse_issue_reference(issue_text)
    paths = pack_paths(issue_ref, workspace)
    paths.root.mkdir(parents=True, exist_ok=True)
    for name in PACK_FILENAMES:
        (paths.root / name).write_text(f"# {name}\n", encoding="utf-8")
    pack = {
        "schema_version": 1,
        "issue": {
            "ref": issue_ref.ref,
            "url": issue_ref.url,
            "title": "Fix agent retrieval bug",
            "state": "open",
            "labels": ["bug", "agent"],
            "assignees": [],
            "comments": 2,
            "repository_stars": 1200,
        },
        "facts": {"repository": issue_ref.repository},
        "inferences": {"score": 82, "contribution_type": "bug fix"},
        "risks": [],
        "unknowns": [],
        "test_guidance": {"status": "not_run", "suggested_commands": ["pytest"]},
        "agent_constraints": ["Do not open a PR, push, commit, or comment on GitHub without explicit user confirmation."],
    }
    manifest = {
        "schema_version": 1,
        "kind": "opensense.pack_manifest",
        "issue_ref": issue_ref.ref,
        "issue_url": issue_ref.url,
        "secret_scan": {"status": "passed"},
        "safety": {"source_modified": False, "github_write_performed": False},
        "generated_files": [*PACK_FILENAMES, "pack.json", "manifest.json"],
    }
    paths.pack_json.write_text(json.dumps(pack), encoding="utf-8")
    paths.manifest_json.write_text(json.dumps(manifest), encoding="utf-8")


def test_test_run_records_successful_command_and_evidence(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(
        app,
        [
            "test",
            "run",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "print('ok')",
        ],
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    run = json.loads((root / "test-run.json").read_text(encoding="utf-8"))
    assert run["issue_ref"] == "owner/repo#7"
    assert run["kind"] == "opensense.test_run"
    assert run["status"] == "passed"
    assert run["exit_code"] == 0
    assert run["github_write_performed"] == "not_asserted"
    assert run["command"][-2:] == ["-c", "print('ok')"]
    assert "ok" in (root / "test-output.log").read_text(encoding="utf-8")
    evidence = (root / "test-run.md").read_text(encoding="utf-8")
    assert "Status: passed" in evidence
    assert "Exit code: 0" in evidence


def test_test_run_records_failed_command_without_success_language(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(
        app,
        [
            "test",
            "run",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--force",
            "--",
            sys.executable,
            "-c",
            "import sys; print('bad'); sys.exit(3)",
        ],
    )

    assert result.exit_code == 1
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    run = json.loads((root / "test-run.json").read_text(encoding="utf-8"))
    assert run["status"] == "failed"
    assert run["exit_code"] == 3
    evidence = (root / "test-run.md").read_text(encoding="utf-8")
    assert "Status: failed" in evidence
    assert "passed" not in evidence.lower()


def test_pr_draft_uses_real_test_result_and_only_writes_local_files(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    issue_ref = parse_issue_reference("owner/repo#7")
    paths = pack_paths(issue_ref, tmp_path)
    assert runner.invoke(
        app,
        [
            "test",
            "run",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "print('ok')",
        ],
    ).exit_code == 0

    result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    draft = (paths.root / "pr-draft.md").read_text(encoding="utf-8")
    metadata = json.loads((paths.root / "pr-draft.json").read_text(encoding="utf-8"))
    assert metadata["kind"] == "opensense.pr_draft"
    assert metadata["github_write_performed"] is False
    assert "Related to owner/repo#7" in draft
    assert "Status: passed" in draft
    assert "Exit code: 0" in draft
    assert "gh pr create" not in result.output


def test_pr_draft_never_claims_tests_passed_when_not_run(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    draft = (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "pr-draft.md").read_text(encoding="utf-8")
    assert "Status: not_run" in draft
    assert "Tests have not been run yet." in draft
    assert "passed" not in draft.lower()


def test_test_run_redacts_full_secret_like_output(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    secret = "ghp_123456789012345678901234567890123456"

    result = runner.invoke(
        app,
        [
            "test",
            "run",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            f"print('{secret}')",
        ],
    )

    assert result.exit_code == 0, result.output
    output = (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "test-output.log").read_text(encoding="utf-8")
    assert secret not in output
    assert "[REDACTED]" in output


def test_pr_draft_downgrades_invalid_test_run_instead_of_claiming_passed(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    (root / "test-run.json").write_text(
        json.dumps(
            {
                "kind": "opensense.test_run",
                "issue_ref": "owner/repo#7",
                "status": "passed",
                "exit_code": 1,
                "command": [sys.executable, "-c", "print('fake')"],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    draft = (root / "pr-draft.md").read_text(encoding="utf-8")
    assert "Status: not_verified" in draft
    assert "passed" not in draft.lower()


def test_pr_draft_marks_test_result_stale_after_local_changes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    assert runner.invoke(
        app,
        [
            "test",
            "run",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "print('ok')",
        ],
    ).exit_code == 0
    (tmp_path / "README.md").write_text("# Demo\n\nChanged after tests.\n", encoding="utf-8")

    result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    draft = (root / "pr-draft.md").read_text(encoding="utf-8")
    assert "Status: stale" in draft
    assert "Status: passed" not in draft


def test_pr_draft_rejects_missing_sandbox_worktree(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    (root / "sandbox.json").write_text(
        json.dumps(
            {
                "issue_ref": "owner/repo#7",
                "sandbox_id": "owner-repo-7",
                "branch_name": "opensense/sandbox/owner-repo-7",
                "worktree_path": str(tmp_path / ".opensense" / "sandboxes" / "owner-repo-7" / "worktree"),
                "real_worktree_path": str(tmp_path / ".opensense" / "sandboxes" / "owner-repo-7" / "worktree"),
                "base_commit": "HEAD",
                "created_at": "2026-01-01T00:00:00+00:00",
                "safety_status": "created",
                "dirty_policy": "clean_required",
                "dirty_snapshot": "",
                "pack_manifest_hash": "abc",
                "operations_allowed": ["git worktree add", "metadata write"],
                "operations_denied": ["git push", "github pr"],
                "source_modified": False,
                "github_write_performed": False,
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "Sandbox worktree no longer exists" in result.output


def test_test_run_detects_indirect_commit_and_pr_draft_downgrades(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(
        app,
        [
            "test",
            "run",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; import subprocess; Path('README.md').write_text('# Demo\\n\\nCommitted by test.\\n', encoding='utf-8'); subprocess.run(['git','add','README.md'], check=True); subprocess.run(['git','commit','-m','test commit'], check=True)",
        ],
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    run = json.loads((root / "test-run.json").read_text(encoding="utf-8"))
    assert run["git_commit_performed"] is True

    draft_result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert draft_result.exit_code == 0, draft_result.output
    draft = (root / "pr-draft.md").read_text(encoding="utf-8")
    assert "Status: not_verified" in draft
