# Phase Two: Agent-Native PR Readiness

This document defines the phase-two direction for OpenSense.

The product should become a contribution preparation layer, not an automatic PR spam bot. The goal is to help a developer decide whether an issue is worth attempting, collect enough evidence, and hand a careful task to a coding agent.

## Product Goal

OpenSense should help users make better PR attempts, not create more PR noise.

Phase two focuses on:

- Turning one issue into a clear context pack.
- Separating facts, inference, and LLM suggestions.
- Estimating whether an issue is suitable for agent-assisted work.
- Preparing PR evidence that is honest about tests, risks, and unknowns.
- Keeping all source-code modification and PR creation out of the default flow.

## P0 Commands

### `opensense pack <issue-url>`

Generate a local context pack:

```text
.opensense/packs/<owner>__<repo>/<issue-number>/
  issue.md
  repo.md
  files.md
  tests.md
  plan.md
  risks.md
  agent.md
  pack.json
  manifest.json
```

The pack should include:

- Issue identity, URL, title, labels, state, and updated time.
- Short problem summary with expected and actual behavior when available.
- Maintainer signals: assignee, linked PRs, maintainer comments, stale signals.
- Contribution hints from README, CONTRIBUTING, issue templates, and PR templates.
- Candidate files or modules, clearly marked as inferred when not certain.
- Suggested verification commands and missing test gaps.
- PR plan, non-goals, risks, and whether to comment before coding.
- Provenance for important claims: GitHub API, repo docs, command output, rules, or LLM.

Default behavior:

- Read GitHub and local repository data.
- Write only under `.opensense/packs/`.
- Do not modify source code.
- Do not create branches, commits, comments, or PRs.

`pack.json` should expose facts, inferences, risks, unknowns, test guidance, agent constraints, and provenance for future MCP tools. `manifest.json` should record generated files, source commit, dirty-worktree state, skipped sensitive paths, and secret scan status.

### `opensense patch <issue-url> --dry-run`

Assess whether an issue is suitable for agent-assisted patch work.

The output should answer:

- Is this issue suitable for a small PR?
- Is it suitable for a coding agent?
- What files are likely involved?
- What evidence is missing?
- What tests or reproduction steps are required?
- Which risks should block automation?

Default behavior:

- Do not write to the source tree.
- Do not create a diff that claims to be applied.
- Do not run destructive commands.
- Do not open PRs or comments.

Suggested thresholds:

- Expected changed files: at most 5.
- Expected changed lines: at most 300.
- Issue should be open, unassigned, and not covered by an active PR.
- There should be a plausible test, reproduction, or verification path.

### `opensense evidence <issue-url>`

Generate PR evidence files after a pack exists:

```text
.opensense/packs/<owner>__<repo>/<issue-number>/
  pr-summary.md
  test-evidence.md
  maintainer-note.md
```

Evidence must be honest:

- If a test was not run, write `not run`.
- If the model inferred something, label it as inference.
- If reproduction is unclear, state the gap.
- If the patch is not applied, do not imply it is applied.

## P1 Direction

### MCP Server

Add an `opensense-mcp` package only after the core pack and evidence logic is stable.

Initial MCP tools should be read-only:

- `get_watchlist`
- `list_daily_candidates`
- `inspect_issue`
- `generate_pr_plan`

Do not expose `apply_patch`, `commit`, `push`, `comment`, or `create_pr` in the first MCP version.

### Agent Handoff

`agent.md` should be written for coding agents and include:

- Goal.
- Context.
- Facts and sources.
- Files to inspect first.
- Tests to run.
- Allowed scope.
- Explicit non-goals.
- Required PR evidence.
- Safety constraints.

It should not instruct an agent to make broad refactors, update dependencies, or touch unrelated files.

## Hard Constraints

- Phase two is read-first and source-code-safe by default.
- No automatic issue comments.
- No automatic branch creation.
- No automatic commits.
- No automatic push.
- No automatic PR creation.
- No batch PR preparation across many issues.
- No fabricated test results.
- No hidden raw API keys in packs, reports, logs, or commits.
- No claims that a PR will be accepted or merged.

## Default Rejections

OpenSense should reject or mark as human-only:

- Security vulnerabilities.
- Authentication, authorization, encryption, privacy, payment, or legal issues.
- License, trademark, or compliance changes.
- Large architecture migrations.
- Breaking public API changes.
- Performance work that requires hard-to-run benchmarks.
- Issues already assigned or covered by an active PR.
- Issues blocked by maintainer design decisions.
- Unclear bugs with no reproduction, logs, failing tests, or maintainer confirmation.
- Large dependency upgrades, formatting sweeps, typo sweeps, or link-promotion changes.

## PR Draft Gate For Later Phases

When OpenSense eventually supports draft PR generation, it should require:

- User confirmation.
- A branch or worktree created explicitly for one issue.
- Small, reviewable diff.
- Real test commands with exit codes.
- Secret scan passed.
- Sensitive file check passed.
- README/CONTRIBUTING/PR template checked.
- Clear risk and limitation notes.
- Draft PR by default.
- No auto review request, auto assign, or aggressive closing keywords.

## Implementation Notes

Recommended module split:

```text
src/opensense/
  core/
    issue_ref.py      # Parse GitHub issue URLs and owner/repo#number refs
    pack.py           # Build context pack data
    evidence.py       # Build PR evidence data
    patch.py          # Evaluate dry-run suitability
    rendering.py      # Render Markdown files
  storage/
    packs.py          # Safe pack paths and file writes
  github/
    repositories.py   # Repo metadata, docs, contribution hints
```

Keep the first implementation boring:

- Use dataclasses, not a database.
- Use Markdown files, not HTML.
- Keep LLM optional.
- Keep MCP as a thin adapter over core services later.
