# Decisions

Use this document for early product, scope, naming, architecture, and trade-off decisions.

Keep decisions lightweight while the project is young. Split into `.docs/decisions/0001-*.md` only when this file becomes hard to scan or decisions need formal ADR-style history.

## Active Decisions

### 2026-06-08: Product name is OpenSense

Decision:

Use `OpenSense` as the project name.

Reason:

- Short and brandable.
- Broader than GitHub-only issue search.
- Suggests sensing open-source contribution opportunities.

Status: accepted

### 2026-06-08: Start as a Python CLI

Decision:

OpenSense starts as a Python CLI, not a Web/SaaS app.

Reason:

- The user's daily workflow is command-line friendly.
- Python is a good fit for GitHub API calls, scoring, local reports, and optional LLM integration.
- A CLI avoids early login, database, hosting, and frontend complexity.

Status: accepted

### 2026-06-08: Watchlist-first instead of broad discovery

Decision:

The MVP starts from user-selected repositories rather than searching all of GitHub by default.

Reason:

- The user wants to follow known projects such as vLLM and OpenClaw.
- Watchlist-first design avoids becoming a GitSense clone.
- It supports a daily contribution habit around projects the user already cares about.

Status: accepted

### 2026-06-08: LLM key should be supported but optional

Decision:

The first version supports LLM configuration in `opensense init`, but core ranking must work without an LLM key.

Reason:

- LLMs are valuable for issue summaries, risk explanations, and PR plans.
- Deterministic scoring is easier to test and trust.
- The CLI should remain useful even when API keys are missing.

Status: accepted

### 2026-06-11: Daily defaults to LLM-assisted finding

Decision:

`opensense daily` should try LLM-assisted finding by default. Users can run `opensense daily --no-llm` for a pure deterministic run.

Reason:

- The valuable AI moment is not only planning a selected issue; it is helping choose which candidate deserves attention today.
- The deterministic score remains the fact layer and fallback.
- `--candidate-pool` gives the LLM a wider but bounded set of issues without turning OpenSense into broad GitHub search.

Status: accepted

### 2026-06-08: MVP command path is daily to issue plan

Decision:

The MVP should optimize the path:

```text
watched repos + skills -> daily candidates -> issue review -> PR plan
```

Reason:

- The product goal is not general open-source intelligence.
- The user wants to find one small issue today and turn it into a serious PR attempt.
- `daily` and `issue --plan` are the strongest habit-forming commands.

Status: accepted

## Open Questions

- Which exact GitHub repo should represent OpenClaw in examples?
- Should the first release publish to PyPI as `opensense` or a scoped fallback name?
- Should the first report format be Markdown only or also static HTML?
