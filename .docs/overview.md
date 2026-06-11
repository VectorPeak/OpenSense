# Overview

OpenSense helps developers build a daily open-source contribution habit.

The target user already knows a few repositories they care about, such as vLLM, Flask, HTTPX, FastAPI, or OpenClaw. They do not need a random issue browser. They need a reliable way to find small, realistic issues from those repositories and turn one of them into a PR attempt.

## Core Promise

Every day, OpenSense should help answer:

- Which watched repositories have approachable issues today?
- Which issues look small enough for a focused PR?
- Which issues have healthier maintainer and mergeability signals?
- Which issue is worth inspecting further?
- What should the user do before opening a PR?

## Product Shape

OpenSense starts as a Python CLI.

The current MVP commands are:

```bash
opensense init
opensense watch repo add <owner/repo>
opensense watch skill add <skill>
opensense daily
opensense issue <owner/repo#issue>
opensense issue <owner/repo#issue> --plan
opensense pack <issue-url>
opensense patch <issue-url> --dry-run
opensense evidence <issue-url>
opensense repo <owner/repo>
```

The first version works without an LLM key. With an LLM key, `daily` can use a larger candidate pool and ask the model to pick the most realistic opportunities, explain risks, and suggest the next `issue --plan` command. `opensense daily --no-llm` keeps the old rule-only path.

Watched skills describe the user's preferred contribution surface, such as `python`, `llm`, `cli`, `tests`, or `github-actions`. `daily` uses them as a lightweight ranking signal before the optional LLM pass.

## Non-Goals

- Do not automatically write patches.
- Do not automatically open PRs.
- Do not guarantee merge success.
- Do not become a general GitHub trend dashboard.
- Do not search all of GitHub by default.

## Phase Two Direction

The next major direction is agent-native PR readiness:

```text
daily candidates -> one issue -> context pack -> risk check -> evidence -> agent handoff
```

Phase two now adds `pack`, `patch --dry-run`, and `evidence` before any automatic patch or PR workflow. See `.docs/phase-two-agent-pr-workflow.md` and `.docs/goal.md`.
