# Local-First Workflow Notes

OpenSense should prepare evidence locally before any GitHub write action.

- Repository context and issue packs are local artifacts.
- Agent attempts should run in an isolated sandbox worktree.
- Test output should be captured before drafting a PR.
- The final decision to push or open a PR remains manual.

This keeps automation useful without crossing project-maintainer boundaries prematurely.
