# Development

OpenSense is a lightweight Python CLI.

## Stack

- Python 3.10+
- Typer for CLI commands
- Rich for terminal output
- httpx for GitHub API calls
- TOML/JSON files for local workspace state
- Optional OpenAI-compatible LLM API for daily finding and issue planning

## Commands

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

`opensense daily` defaults to LLM-assisted finding. It first fetches GitHub issues and applies deterministic scoring, then passes a bounded candidate pool to the LLM if a key is configured. Use `opensense daily --no-llm` to keep the command fully rule-based.

## Runtime State

```text
.opensense/
  config.toml
  watchlist.toml
  cache/
  packs/
  reports/
```

Example `watchlist.toml`:

```toml
skills = ["agent", "rag"]

[[repositories]]
name = "openclaw/openclaw"

[[repositories]]
name = "vllm-project/vllm"

[[repositories]]
name = "openai/codex"

[[repositories]]
name = "sgl-project/sglang"

[[repositories]]
name = "langchain-ai/langchain"

[[repositories]]
name = "run-llama/llama_index"
```

## Implementation Notes

- Keep deterministic scoring usable without LLM.
- Use LLM for daily candidate interpretation, summaries, risk explanations, and PR plans.
- Treat GitHub API data and deterministic scoring as the fact layer; LLM output should explain and prioritize, not invent state.
- Keep phase-two PR readiness commands read-first: `pack` and `evidence` write only under `.opensense/packs/`, while `patch --dry-run` must not modify source files.
- Keep cache simple until cross-day analytics becomes necessary.
- Prefer Markdown/Rich output before building a complex HTML report.
