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


def test_agent_status_json_reports_steps_and_next_step(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)

    result = runner.invoke(app, ["agent", "status", "owner/repo#7", "--json", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["issue_ref"] == "owner/repo#7"
    assert payload["next_step"] == "opensense propose owner/repo#7"
    assert payload["steps"][0]["step"] == "Pack"
    assert payload["steps"][0]["status"] == "ready"


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


def test_agent_handoff_rejects_missing_patch_proposal_without_artifacts(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)
    paths.patch_proposal_md.unlink()

    result = runner.invoke(app, ["agent", "handoff", "owner/repo#7", "--workspace", str(tmp_path)])

    assert result.exit_code == 1
    assert "Patch proposal not found" in result.output
    assert not paths.agent_handoff_json.exists()
    assert not paths.agent_handoff_md.exists()


def test_agent_apply_rejects_sandbox_json_pointing_outside_sandbox_root(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)
    outside = tmp_path / "outside-worktree"
    outside.mkdir()
    sandbox = json.loads(paths.sandbox_json.read_text(encoding="utf-8"))
    sandbox["real_worktree_path"] = str(outside)
    paths.sandbox_json.write_text(json.dumps(sandbox), encoding="utf-8")

    result = runner.invoke(
        app,
        ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", sys.executable, "-c", "print('nope')"],
    )

    assert result.exit_code == 1
    assert "must stay inside" in result.output
    assert not paths.agent_apply_json.exists()
    assert not paths.agent_output_log.exists()


def test_agent_apply_timeout_records_partial_redacted_output(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)
    secret = "sk-123456789012345678901234567890"

    result = runner.invoke(
        app,
        [
            "agent",
            "apply",
            "owner/repo#7",
            "--workspace",
            str(tmp_path),
            "--timeout",
            "1",
            "--",
            sys.executable,
            "-c",
            f"import time, sys; print('{secret}', flush=True); time.sleep(5)",
        ],
    )

    assert result.exit_code == 1
    metadata = json.loads(paths.agent_apply_json.read_text(encoding="utf-8"))
    output = paths.agent_output_log.read_text(encoding="utf-8")
    assert metadata["status"] == "timeout"
    assert metadata["exit_code"] is None
    assert metadata["redaction_applied"] is True
    assert secret not in output
    assert "[REDACTED]" in output


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


def test_attempt_list_and_open_read_local_artifacts(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["agent", "handoff", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0

    listed = runner.invoke(app, ["attempt", "list", "--json", "--workspace", str(tmp_path)])
    opened = runner.invoke(app, ["attempt", "open", "owner/repo#7", "--json", "--workspace", str(tmp_path)])

    assert listed.exit_code == 0, listed.output
    list_payload = json.loads(listed.output)
    assert list_payload["attempts"][0]["issue_ref"] == "owner/repo#7"
    assert list_payload["attempts"][0]["status"] == "ready_for_apply"
    assert opened.exit_code == 0, opened.output
    open_payload = json.loads(opened.output)
    assert open_payload["issue_ref"] == "owner/repo#7"
    assert open_payload["agent_handoff"].endswith("agent-handoff.md")
    assert open_payload["pr_draft"] is None


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


def test_agent_apply_rejects_git_global_option_remote_writes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)

    push = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", "git", "-C", ".", "push"])
    commit = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", "git", "-c", "user.name=x", "commit", "-m", "x"])
    gh_api = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", "gh", "api", "repos/owner/repo/issues/7/comments"])

    assert push.exit_code == 1
    assert "Refusing" in push.output
    assert commit.exit_code == 1
    assert "Refusing" in commit.output
    assert gh_api.exit_code == 1
    assert "Refusing" in gh_api.output
    assert not paths.agent_apply_json.exists()


def test_agent_apply_rejects_common_gh_write_verbs(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_pack(tmp_path)
    assert runner.invoke(app, ["propose", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["sandbox", "create", "owner/repo#7", "--workspace", str(tmp_path)]).exit_code == 0
    paths = pack_paths(parse_issue_reference("owner/repo#7"), tmp_path)

    commands = [
        ["gh", "issue", "edit", "owner/repo#7", "--add-label", "bug"],
        ["gh", "issue", "close", "owner/repo#7"],
        ["gh", "pr", "merge", "123"],
        ["gh", "release", "create", "v1.0.0"],
        ["gh", "workflow", "run", "ci.yml"],
        ["gh", "--repo", "owner/repo", "issue", "edit", "7", "--add-label", "bug"],
    ]

    for command in commands:
        result = runner.invoke(app, ["agent", "apply", "owner/repo#7", "--workspace", str(tmp_path), "--", *command])

        assert result.exit_code == 1, command
        assert "Refusing" in result.output
    assert not paths.agent_apply_json.exists()


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
