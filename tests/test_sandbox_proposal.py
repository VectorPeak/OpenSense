import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from opensense.cli import app
from opensense.core.issue_ref import parse_issue_reference
from opensense.core.sandbox import create_sandbox
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
        "inferences": {
            "score": 82,
            "contribution_type": "bug fix",
            "candidate_file_searches": ["rg -n \"agent\" ."],
        },
        "risks": [],
        "unknowns": ["Local reproduction has not been attempted."],
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


def test_patch_propose_writes_proposal_without_source_changes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    before = (tmp_path / "README.md").read_text(encoding="utf-8")

    result = runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    proposal = tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "patch-proposal.md"
    assert proposal.exists()
    text = proposal.read_text(encoding="utf-8")
    assert "Patch Proposal" in text
    assert "Stop Conditions" in text
    assert "pytest" in text
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == before
    assert git(tmp_path, "status", "--porcelain").stdout.strip() == ""


def test_sandbox_create_writes_audited_worktree_metadata(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    sandbox = json.loads((root / "sandbox.json").read_text(encoding="utf-8"))
    assert sandbox["issue_ref"] == "owner/repo#7"
    assert sandbox["branch_name"].startswith("opensense/sandbox/")
    assert sandbox["source_modified"] is False
    assert sandbox["github_write_performed"] is False
    assert sandbox["dirty_policy"] == "clean_required"
    assert sandbox["pack_manifest_hash"]
    assert Path(sandbox["real_worktree_path"]).exists()
    assert str(Path(sandbox["real_worktree_path"]).resolve()).startswith(str((tmp_path / ".opensense" / "sandboxes").resolve()))


def test_sandbox_create_rejects_dirty_workspace_by_default(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    (tmp_path / "README.md").write_text("# Dirty\n", encoding="utf-8")

    result = runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "uncommitted changes" in result.output
    assert not (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "sandbox.json").exists()


def test_sandbox_create_allow_dirty_records_snapshot(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    (tmp_path / "README.md").write_text("# Dirty\n", encoding="utf-8")

    result = runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--allow-dirty", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    sandbox_path = tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "sandbox.json"
    sandbox = json.loads(sandbox_path.read_text(encoding="utf-8"))
    assert sandbox["dirty_policy"] == "allowed"
    assert "README.md" in sandbox["dirty_snapshot"]


def test_sandbox_status_reads_existing_metadata(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["sandbox", "status", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "opensense/sandbox/" in result.output


def test_sandbox_create_rejects_worktree_path_outside_sandbox_root(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    issue_ref = parse_issue_reference("owner/repo#7")
    outside = tmp_path / "escape-worktree"

    try:
        create_sandbox(issue_ref, tmp_path, worktree_path=outside)
    except ValueError as exc:
        assert "must stay inside" in str(exc)
    else:
        raise AssertionError("create_sandbox accepted a worktree outside the sandbox root")

    assert not outside.exists()
    assert not (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "sandbox.json").exists()


def test_sandbox_create_rejects_existing_branch_without_worktree_side_effects(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert git(tmp_path, "branch", "opensense/sandbox/owner-repo-7").returncode == 0

    result = runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "branch already exists" in result.output
    assert not (tmp_path / ".opensense" / "sandboxes" / "owner-repo-7" / "worktree").exists()
    assert not (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "sandbox.json").exists()


def test_sandbox_create_rejects_merge_in_progress(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    (tmp_path / ".git" / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")

    result = runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "merge in progress" in result.output
    assert not (tmp_path / ".opensense" / "sandboxes" / "owner-repo-7" / "worktree").exists()


def test_sandbox_create_reports_non_git_workspace_before_dirty_message(tmp_path: Path) -> None:
    write_valid_pack(tmp_path)

    result = runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "git metadata unavailable" in result.output
    assert "uncommitted changes" not in result.output
