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

The intended MVP commands are:

```bash
opensense init
opensense watch add <owner/repo>
opensense daily
opensense inspect <owner/repo#issue>
opensense plan <owner/repo#issue>
```

The first version should work without an LLM key. With an LLM key, it should produce better summaries, risk explanations, and PR plans.

## Non-Goals

- Do not automatically write patches.
- Do not automatically open PRs.
- Do not guarantee merge success.
- Do not become a general GitHub trend dashboard.
- Do not search all of GitHub by default.
