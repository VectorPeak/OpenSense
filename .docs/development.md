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
opensense watch add <owner/repo>
opensense daily
opensense inspect <owner/repo#issue>
opensense plan <owner/repo#issue>
```

## Runtime State

```text
.opensense/
  config.toml
  watchlist.toml
  cache/
  reports/
```

## Implementation Notes

- Keep deterministic scoring usable without LLM.
- Use LLM only for summaries, risk explanations, and PR plans.
- Keep cache simple until cross-day analytics becomes necessary.
- Prefer Markdown/Rich output before building a complex HTML report.
