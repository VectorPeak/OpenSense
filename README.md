<div align="center">

# OpenSense

Daily PR opportunity finder for known open-source repositories

![status](https://img.shields.io/badge/status-mvp%20cli-15803D)
![python](https://img.shields.io/badge/python-3.10+-blue)
![cli](https://img.shields.io/badge/interface-CLI-07C983)
![llm](https://img.shields.io/badge/LLM-optional-purple)

简体中文 | English later

</div>

```text
known repos  ->  daily issue ranking  ->  issue --plan  ->  PR attempt
```

## 项目简介

OpenSense 是一个 Python CLI，目标是帮助开发者每天从自己关注的知名 GitHub 开源项目里，找到“小而靠谱、较可能被合并”的 issue，并在动手前生成一份 PR 前计划。

它不是全网 issue 搜索器，也不是自动写 PR 的机器人。OpenSense 更像一个个人开源贡献工作台：你维护一份 watchlist，例如 `vllm-project/vllm`、`pallets/flask`、`encode/httpx`，OpenSense 每天扫描这些项目，筛出更适合今天下手的小 issue。

没有 LLM key 也能运行：默认使用规则评分。有 LLM key 时，可以获得更深入的 issue 分析、风险判断和 PR 前计划。

## Why OpenSense

参与开源项目时，真正耗时间的往往不是“点开 issue”，而是判断：

- 这个 issue 是否足够小？
- 有没有人已经在做？
- 维护者是否认可这个方向？
- 它是 bug fix、test、docs，还是一个大 feature？
- 我应该直接开 PR，还是先留言确认？
- 做这个 PR 之前应该先读哪些内容、跑哪些测试？

OpenSense 试图把这个判断流程沉淀成每天可重复的命令行工作流。

```text
daily browsing  ->  short candidate list  ->  focused issue analysis  ->  PR-ready plan
```

## Quick Start

OpenSense currently ships an MVP CLI with five top-level commands:

```text
init -> watch -> daily -> issue -> repo
```

```bash
# 1. Create local OpenSense config
opensense init

# 2. Add repositories you care about
opensense watch add vllm-project/vllm
opensense watch add pallets/flask
opensense watch add encode/httpx

# 3. Check local config and optional API env vars
opensense init --check

# 4. Get today's PR candidates
opensense daily

# 5. Inspect one promising issue and optionally generate a PR plan
opensense issue vllm-project/vllm#12345
opensense issue vllm-project/vllm#12345 --plan --no-llm

# 6. Check whether repositories look PR-friendly
opensense repo vllm-project/vllm --skills python,llm
opensense repo vllm-project/vllm pallets/flask --skills python
```

LLM is optional. If configured, it improves issue summaries and PR planning:

```bash
export OPENSENSE_LLM_API_KEY=...
export OPENSENSE_LLM_BASE_URL=https://api.openai.com/v1
export OPENSENSE_LLM_MODEL=gpt-5.5
opensense init --llm-api-key-env OPENSENSE_LLM_API_KEY
```

OpenSense also reads `GITHUB_TOKEN` by default for GitHub API rate limits. It should never store raw API keys in committed files. Configuration should reference environment variables.

## Core Workflow

The MVP path is implemented as a thin CLI. Network-backed commands use the GitHub API and deterministic rules first; LLM support is optional.

### 1. Initialize

```bash
opensense init
```

Creates local state:

```text
.opensense/
  config.toml
  watchlist.toml
  cache/
  reports/
```

`init` should configure:

- GitHub token environment variable
- LLM provider and model
- LLM API key environment variable
- daily ranking preferences
- local cache/report paths

### 2. Watch Known Repositories

```bash
opensense watch add vllm-project/vllm
```

OpenSense is watchlist-first. It starts from repositories you intentionally care about instead of searching the whole internet by default.

### 3. Get Daily Candidates

```bash
opensense daily
```

The daily command scans watched repositories and returns a short list of candidate issues.

Useful filters:

```bash
opensense daily --min-stars 500 --updated-days 14 --max-comments 10 --limit 5
```

Each recommendation explains:

- total score
- likely contribution type
- why it looks approachable
- suggested next command

Example output:

```text
Daily PR candidates

#  Issue                    Score  Type      Why                         Next
1  vllm-project/vllm#12345  82     bug fix   good first issue label      opensense issue vllm-project/vllm#12345
```

### 4. Inspect And Plan An Issue

```bash
opensense issue vllm-project/vllm#12345
opensense issue vllm-project/vllm#12345 --plan
```

`issue` answers:

- What is this issue about?
- Does it look like bug fix, tests, docs, or feature work?
- Is it suitable for a small PR?
- Which deterministic signals make it look approachable?
- Which rule-based risks should you check before coding?

`issue --plan` turns one candidate issue into a pre-PR checklist:

- problem summary
- likely contribution type
- first files or modules to inspect
- suggested implementation path
- test and validation checklist
- whether to comment before coding
- PR title/body draft outline

### 5. Evaluate Repositories

```bash
opensense repo vllm-project/vllm --skills python,llm
```

`repo` checks lightweight repository signals before you spend serious time on a PR:

- repository stars
- recent merged PRs
- open PR backlog
- stale PR ratio
- external contributor merges
- language and skill overlap

## Selection Criteria

OpenSense prefers issues that look:

- small enough for a focused PR
- recently active
- unassigned
- not already covered by a linked PR
- supported by maintainer signals
- likely to be bug fix, test, docs, CI, typing, examples, or narrow behavior fixes
- clear enough to reproduce or verify

OpenSense should down-rank issues that look:

- stale or abandoned
- heavily debated without conclusion
- blocked on design decisions
- already claimed by another contributor
- likely to require broad architecture changes
- dependent on private context, hard benchmarks, or unclear reproduction

## MVP Scope

OpenSense v1 focuses on contribution triage and planning.

It currently does:

- maintain a local watchlist of GitHub repositories
- initialize `.opensense/` local state
- check local config and optional environment variables with `init --check`
- scan open issues from watched repositories with GitHub API
- rank candidates using deterministic rule-based signals
- optionally use LLMs for deeper inspection and PR planning
- generate a pre-PR plan before the user starts coding
- run lightweight repository signal checks before deeper PR investment

It does not yet:

- automatically modify code
- open pull requests for the user
- guarantee that a PR will be accepted or merged
- replace reading issue threads and contributor guides
- search all of GitHub by default
- act as a project management or notification platform

## LLM Philosophy

LLM support is useful, but OpenSense should not depend on it for basic operation.

Recommended split:

```text
GitHub API + deterministic scoring  ->  candidate ranking
LLM-assisted reasoning              ->  summaries, risks, PR plans
```

The LLM should explain and plan; it should not be the only source of truth.

## How OpenSense Is Different

| Tool | Best for | Search scope | Main output |
| --- | --- | --- | --- |
| GitSense | Finding issues across GitHub that match your skills | Broad GitHub search | Ranked issue matches and repo radar |
| good-first-issue / up-for-grabs | Browsing beginner-friendly issue catalogs | Public curated lists | Links to labeled issues |
| OpenSense | Building a daily contribution workflow around repos you care about | Your watchlist | Daily candidates and PR-ready plans |

OpenSense is not trying to know everything about open source. It optimizes one action:

> Find one small issue today that is worth turning into a serious PR attempt.

## Planned Architecture

The current MVP keeps command wiring in a single `cli.py` and splits domain logic by responsibility:

```text
src/opensense/
  cli.py
  config.py
  doctor.py
  models.py

  github/
    client.py
    issues.py
    radar.py

  core/
    radar.py
    scoring.py
    ranking.py
    planner.py

  llm/
    client.py

  storage/
    watchlist.py
```

The first implementation should stay thin: Typer/Rich CLI, GitHub API client, TOML/JSON local state, deterministic scoring, and optional LLM-assisted planning.

## Status

OpenSense currently has the first runnable MVP CLI:

- `opensense init`
- `opensense watch add`
- `opensense watch list`
- `opensense daily`
- `opensense issue`
- `opensense repo`

## License

License has not been selected yet.
