# Agent Guide

Use progressive disclosure. Read only the smallest document needed for the current task.

Keep this file under 300 lines. Move detailed guidance into `.docs/`.

## Read By Task

- Understand the project: `.docs/overview.md`
- Run, build, or configure locally: `.docs/development.md`
- Check early decisions and trade-offs: `.docs/decisions.md`

## Product Boundary

OpenSense is a daily PR opportunity finder for known open-source repositories.

The MVP should optimize:

```text
watched repos + skills -> daily candidates -> issue review -> PR plan
```

Avoid expanding the first version into a general open-source intelligence dashboard.

`opensense daily` defaults to LLM-assisted finding when an LLM key is configured. It still shows the deterministic candidate table first, and `opensense daily --no-llm` keeps the flow fully rule-based.

## Highest Priority Rules

- Preserve user changes.
- Keep README and docs honest about implementation status.
- Do not claim commands are implemented before code exists.
- Do not overwrite existing files unless explicitly asked.
- Ask before destructive actions or broad dependency changes.
- Run relevant verification before claiming work is complete.
