import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from opensense.cli import app
from opensense.storage.packs import pack_paths
from opensense.core.issue_ref import parse_issue_reference

from test_sandbox_proposal import init_git_repo, write_valid_pack


runner = CliRunner()


def test_agent_handoff_writes_local_task_brief(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["agent", "handoff", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    root = tmp_path / ".opensense" / "packs" / "owner__repo" / "7"
    metadata = json.loads((root / "agent-handoff.json").read_text(encoding="utf-8"))
    brief = (root / "agent-handoff.md").read_text(encoding="utf-8")
    assert metadata["kind"] == "opensense.agent_handoff"
    assert metadata["github_write_performed"] is False
    assert "Sandbox worktree" in brief
    assert "Do not commit, push, open a PR, or comment on GitHub." in brief
    assert "patch-proposal.md" in brief


def test_agent_status_reports_next_step_from_partial_attempt(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(app, ["agent", "status", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Pack" in result.output
    assert "Proposal" in result.output
    assert "missing" in result.output
    assert "Next: opensense propose owner/repo#7" in result.output


def test_agent_apply_runs_only_in_sandbox_and_records_diff(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    issue_ref = parse_issue_reference("owner/repo#7")
    paths = pack_paths(issue_ref, tmp_path)
    sandbox = json.loads(paths.sandbox_json.read_text(encoding="utf-8"))

    result = runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; Path('README.md').write_text('# Demo\\n\\nAgent change.\\n', encoding='utf-8'); print('changed')",
        ],
    )

    assert result.exit_code == 0, result.output
    metadata = json.loads(paths.agent_apply_json.read_text(encoding="utf-8"))
    assert metadata["kind"] == "opensense.agent_apply"
    assert metadata["issue_ref"] == "owner/repo#7"
    assert metadata["cwd"] == sandbox["real_worktree_path"]
    assert metadata["exit_code"] == 0
    assert metadata["source_modified"] is True
    assert metadata["git_commit_performed"] is False
    assert metadata["git_push_performed"] == "not_asserted"
    assert metadata["github_write_performed"] == "not_asserted"
    assert "README.md" in metadata["modified_files"]
    assert "changed" in paths.agent_output_log.read_text(encoding="utf-8")
    assert "Agent change" in paths.diff_patch.read_text(encoding="utf-8")
    assert "README.md" in paths.diffstat_txt.read_text(encoding="utf-8")
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "# Demo\n"


def test_agent_apply_requires_proposal_and_sandbox(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    missing_proposal = runner.invoke(
        app,
        ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", sys.executable, "-c", "print('nope')"],
    )

    assert missing_proposal.exit_code == 1
    assert "patch proposal" in missing_proposal.output.lower()
    assert not (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "agent-apply.json").exists()


def test_pr_draft_includes_agent_apply_diff_summary(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; Path('README.md').write_text('# Demo\\n\\nAgent change.\\n', encoding='utf-8')",
        ],
    ).exit_code == 0

    result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    draft = (tmp_path / ".opensense" / "packs" / "owner__repo" / "7" / "pr-draft.md").read_text(encoding="utf-8")
    assert "## Agent Apply" in draft
    assert "Status: passed" in draft
    assert "README.md" in draft


def test_agent_status_reports_full_attempt_ready(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["agent", "handoff", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; Path('README.md').write_text('# Demo\\n\\nAgent change.\\n', encoding='utf-8')",
        ],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["test", "run", "owner/repo#7", "--workspace", str(tmp_path), "--", sys.executable, "-c", "print('ok')"],
    ).exit_code == 0
    assert runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["agent", "status", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Agent handoff" in result.output
    assert "Agent apply" in result.output
    assert "Tests" in result.output
    assert "PR draft" in result.output
    assert "Review pr-draft.md" in result.output


def test_agent_apply_rejects_obvious_remote_write_commands(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0

    direct = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", "git.exe", "push"])
    shell = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", "cmd", "/c", "git push"])

    assert direct.exit_code == 1
    assert "Refusing" in direct.output
    assert shell.exit_code == 1
    assert "shell wrapper" in shell.output


def test_agent_apply_records_untracked_files_in_diffstat(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)

    result = runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; Path('NEW.md').write_text('new file\\n', encoding='utf-8')",
        ],
    )

    assert result.exit_code == 0, result.output
    metadata = json.loads(paths.agent_apply_json.read_text(encoding="utf-8"))
    assert "NEW.md" in metadata["modified_files"]
    assert "Untracked files:" in paths.diffstat_txt.read_text(encoding="utf-8")
    assert "NEW.md" in paths.diffstat_txt.read_text(encoding="utf-8")


def test_agent_apply_captures_staged_diff_against_head(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)

    result = runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; import subprocess; Path('README.md').write_text('# Demo\\n\\nStaged.\\n', encoding='utf-8'); subprocess.run(['git','add','README.md'], check=True)",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Staged" in paths.diff_patch.read_text(encoding="utf-8")
    assert "README.md" in paths.diffstat_txt.read_text(encoding="utf-8")


def test_agent_apply_records_rename_target_path(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)

    result = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", "git", "mv", "README.md", "RENAMED.md"])

    assert result.exit_code == 0, result.output
    metadata = json.loads(paths.agent_apply_json.read_text(encoding="utf-8"))
    assert "RENAMED.md" in metadata["modified_files"]
    assert "README.md" not in metadata["modified_files"]


def test_agent_apply_redacts_secret_like_text_from_diff_patch(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)
    secret = "ghp_123456789012345678901234567890123456"

    result = runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            f"from pathlib import Path; Path('README.md').write_text('# Demo\\n\\n{secret}\\n', encoding='utf-8')",
        ],
    )

    assert result.exit_code == 0, result.output
    diff = paths.diff_patch.read_text(encoding="utf-8")
    assert secret not in diff
    assert "[REDACTED]" in diff


def test_agent_apply_detects_indirect_commit_and_pr_draft_downgrades(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)

    result = runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; import subprocess; Path('README.md').write_text('# Demo\\n\\nCommitted.\\n', encoding='utf-8'); subprocess.run(['git','add','README.md'], check=True); subprocess.run(['git','commit','-m','agent commit'], check=True)",
        ],
    )

    assert result.exit_code == 0, result.output
    metadata = json.loads(paths.agent_apply_json.read_text(encoding="utf-8"))
    assert metadata["git_commit_performed"] is True

    draft_result = runner.invoke(app, ["pr", "draft", "owner/repo#7", "--workspace", str(tmp_path)])

    assert draft_result.exit_code == 0, draft_result.output
    draft = paths.pr_draft_md.read_text(encoding="utf-8")
    assert "Status: not_verified" in draft
    assert "No commit, push" not in draft
