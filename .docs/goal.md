# /goal: Phase Two Execution Target

Goal:

Build OpenSense into an agent-native PR readiness workflow.

OpenSense should help a developer move from:

```text
daily candidates -> one issue -> context pack -> risk check -> evidence -> agent handoff
```

It should not move directly to:

```text
daily candidates -> automatic patch -> automatic PR
```

## Required Build Order

1. Implement `opensense pack <issue-url>`.
2. Implement stable pack storage under `.opensense/packs/<owner>__<repo>/<issue-number>/`.
3. Implement `opensense patch <issue-url> --dry-run` as a read-only suitability report.
4. Implement `opensense evidence <issue-url>` based on an existing pack.
5. Add read-only MCP tools after the CLI core is stable.
6. Consider controlled patch application only after packs, evidence, and dry-run gates are reliable.

## Acceptance Criteria

- Works without an LLM key.
- LLM output is optional and labeled as inference when appropriate.
- No command modifies source code by default.
- No command opens PRs, comments, commits, or pushes in phase two.
- Every generated pack separates facts, inference, suggested actions, risks, and unknowns.
- Tests cover issue ref parsing, pack path generation, file writing, no-overwrite behavior, and dry-run non-modification.

## Non-Negotiable Safety Rules

- Never fabricate test results.
- Never package secrets.
- Never present model guesses as repository facts.
- Never automate security, auth, privacy, payment, legal, or license fixes.
- Never optimize for PR volume over PR quality.
