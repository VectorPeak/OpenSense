# Development

OpenSense is currently in planning/prototype setup.

## Planned Stack

- Python 3.10+
- Typer for CLI commands
- Rich for terminal output
- httpx for GitHub API calls
- TOML/JSON files for local workspace state
- Optional OpenAI-compatible LLM API

## Planned Commands

```bash
opensense init
opensense watch repo add <owner/repo>
opensense watch skill add <skill>
opensense daily
opensense issue <owner/repo#issue>
opensense issue <owner/repo#issue> --plan
opensense repo <owner/repo>
```

## Runtime State

```text
.opensense/
  config.toml
  watchlist.toml
  cache/
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
- Use LLM only for summaries, risk explanations, and PR plans.
- Keep cache simple until cross-day analytics becomes necessary.
- Prefer Markdown/Rich output before building a complex HTML report.
