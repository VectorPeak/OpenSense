<div align="center">

# OpenSense

面向知名开源项目的每日 PR 机会发现工具

![status](https://img.shields.io/badge/status-mvp%20cli-15803D)
![python](https://img.shields.io/badge/python-3.10+-blue)
![cli](https://img.shields.io/badge/interface-CLI-07C983)
![llm](https://img.shields.io/badge/LLM-optional-purple)

简体中文

</div>

```text
watchlist -> daily -> issue --plan -> pack -> propose -> sandbox
          -> agent apply -> test run -> pr draft -> agent status
```

## 解决痛点

想给知名开源项目提交 PR，但每天真正卡住的不是写代码，而是选题。翻很多 issue，常常会遇到：描述不清、范围太大、已经有人在做、维护者可能不接受、或者项目最近根本不太合并外部贡献。

OpenSense 关注的是更实际的开源贡献流程：先从你自己关心的仓库开始，例如 vLLM、FastAPI、HTTPX，再结合你的技术栈标签，例如 `python`、`llm`、`cli`、`tests`，每天筛出更值得打开的小 issue。

它会优先看 issue 是否近期更新、评论是否过多、是否无人认领、标签是否偏 bug fix 或 tests、仓库 star 和 PR 合并信号是否健康，并在你动手前生成一份 PR 前计划，帮助你判断：这个 issue 值不值得做、应该先读哪里、要补哪些测试、是否应该先留言确认。

## 项目简介

OpenSense 是一个 Python CLI，目标是帮助开发者每天从自己关注的知名 GitHub 开源项目里，找到“小而靠谱、较可能被合并”的 issue，并在动手前生成一份 PR 前计划。

它不是全网 issue 搜索器，也不是自动写 PR 的机器人。OpenSense 更像一个个人开源贡献工作台：初始化时会提供一份以 Agent、RAG 和推理基础设施为主的默认 watchlist，你也可以继续加入自己关心的仓库和技术栈。OpenSense 每天扫描这些项目，筛出更适合今天下手的小 issue。

没有 LLM key 也能运行：OpenSense 会先用规则评分做基础排序；有 LLM key 时，`daily` 会默认追加候选解释、风险判断和下一步建议。

## 为什么做 OpenSense

参与开源项目时，真正耗时间的往往不是“点开 issue”，而是判断：

- 这个 issue 是否足够小？
- 有没有人已经在做？
- 维护者是否认可这个方向？
- 它是 bug fix、test、docs，还是一个大 feature？
- 我应该直接开 PR，还是先留言确认？
- 做这个 PR 之前应该先读哪些内容、跑哪些测试？

OpenSense 试图把这个判断流程沉淀成每天可重复的命令行工作流。

```text
每日浏览  ->  候选 issue 短列表  ->  单个 issue 分析  ->  PR 前计划
```

## 快速开始

OpenSense 已发布到 PyPI。安装包名是 `opensense-vp`，安装后的命令名是 `opensense`。

```bash
pip install opensense-vp
```

当前 CLI 围绕一条本地 PR 尝试流程组织命令：

```text
init -> watch -> daily -> issue -> pack -> patch -> propose
     -> sandbox -> agent -> test -> pr -> repo
```

```bash
# 1. 安装并创建本地 OpenSense 配置
pip install opensense-vp
opensense init

# 2. 查看默认仓库和技术栈，并按需扩展
opensense watch repo list
opensense watch skill list
opensense watch repo add microsoft/autogen
opensense watch repo add deepset-ai/haystack
opensense watch skill add python

# 3. 检查本地配置和可选 API 环境变量
opensense init --check

# 4. 获取今天值得看的 PR 候选 issue
opensense daily
opensense daily --candidate-pool 50
opensense daily --no-llm

# 5. 分析一个候选 issue，并可选生成 PR 前计划
opensense issue vllm-project/vllm#12345
opensense issue vllm-project/vllm#12345 --plan --no-llm

# 6. 把单个 issue 变成本地 PR 尝试
opensense pack https://github.com/vllm-project/vllm/issues/12345
opensense patch https://github.com/vllm-project/vllm/issues/12345 --dry-run
opensense propose https://github.com/vllm-project/vllm/issues/12345
opensense sandbox create https://github.com/vllm-project/vllm/issues/12345
opensense agent handoff https://github.com/vllm-project/vllm/issues/12345
opensense agent apply https://github.com/vllm-project/vllm/issues/12345 -- <agent command>
opensense test run https://github.com/vllm-project/vllm/issues/12345 -- <test command>
opensense pr draft https://github.com/vllm-project/vllm/issues/12345
opensense agent status https://github.com/vllm-project/vllm/issues/12345

# 7. 判断仓库是否适合投入 PR
opensense repo vllm-project/vllm --skills python,llm
opensense repo vllm-project/vllm pallets/flask --skills python
```

## 效果演示

`opensense init` 默认会加入 OpenClaw、vLLM、Codex、SGLang、LangChain 和 LlamaIndex，并把 `agent`、`rag` 作为默认技术栈：

```text
$ opensense watch repo list
openclaw/openclaw
vllm-project/vllm
openai/codex
sgl-project/sglang
langchain-ai/langchain
run-llama/llama_index

$ opensense watch skill list
agent
rag
```

然后运行 `opensense daily`，你会先得到一份短候选列表，而不是继续在 GitHub 页面里反复翻 issue：

```text
$ opensense daily --min-stars 1000 --limit 8

找到 24 个候选 issue。
正在按仓库信号、issue 小型程度和技能匹配度排序...

OpenSense 结果
技术栈：agent, rag
结果：8 个 issue，按适合今天动手的程度排序

1. [9/10] vllm-project/vllm
   Fix CUDA graph memory leak in speculative decoding
   Labels: bug, good first issue
   为什么匹配：推理基础设施是 Agent / RAG 应用的重要运行底座。
   怎么上手：先看 vllm/spec_decode/worker.py 和相关 graph capture 测试。
   下一步：opensense issue vllm-project/vllm#12345 --plan

2. [8/10] triton-lang/triton
   Type inference fails for constexpr in nested loops
   Labels: bug
   为什么匹配：GPU kernel 和高性能推理相关。
   怎么上手：查 code_generator.py visit_For，并对照相似 issue。
   下一步：opensense issue triton-lang/triton#9547 --plan

3. [7/10] huggingface/transformers
   ...
```

默认情况下，`daily` 会在规则粗排后尝试使用 LLM 从更大的候选池里继续帮你找：

```bash
opensense daily
opensense daily --candidate-pool 50
```

这时 OpenSense 会先用 GitHub API 拉取更多候选 issue，再用确定性规则做粗排，最后把候选池交给 LLM 判断：今天优先看哪几个、为什么、有哪些风险，以及下一条应该执行的 `opensense issue ... --plan` 命令。

如果你只想使用规则排序，可以关闭 LLM：

```bash
opensense daily --no-llm
```

选中一个 issue 后，再用 `issue --plan` 生成 PR 前计划：

```text
$ opensense issue vllm-project/vllm#12345 --plan

Score: 86
Type: test
Why:
+ matches watched skill: python
+ unassigned
+ recent activity

# PR Plan for vllm-project/vllm#12345

- 先阅读 issue 描述、最近评论和相关测试失败信息。
- 优先定位 scheduler / tests 相关模块，确认是否能复现。
- 先补一个最小失败测试，再做窄范围修复。
- 提交 PR 前运行相关单测，并在 PR 描述里写清楚复现方式和验证命令。
- 如果 issue 里没有维护者确认，可以先留言说明计划，避免做偏方向。
```

如果你还不确定某个仓库是否值得投入时间，可以先看仓库级信号：

```text
$ opensense repo vllm-project/vllm --skills python,llm

Repository        Score  Verdict  Signals
vllm-project/vllm 82     Go       external contributors are getting merged; language matches your skills
```

进入本地 PR 尝试后，OpenSense 会把证据都放在同一个 issue 目录下，`agent status` 会读取这些文件并告诉你下一步：

```text
.opensense/packs/<owner>__<repo>/<issue>/
  issue.md
  pack.json
  manifest.json
  patch-proposal.md
  sandbox.json
  agent-handoff.md
  agent-apply.json
  diff.patch
  test-run.md
  pr-draft.md
```

## 核心流程

当前 MVP 是一个轻量 CLI。需要网络的命令优先使用 GitHub API 和确定性规则；LLM 只作为可选增强。

### 1. 初始化

```bash
opensense init
```

创建本地状态目录：

```text
.opensense/
  config.toml
  watchlist.toml
  cache/
  reports/
```

`init` 负责配置：

- GitHub token 环境变量名
- LLM 服务和模型
- LLM API key 环境变量名
- 每日排序偏好
- 本地缓存和报告路径

首次执行 `init` 会创建一份可直接使用的默认 watchlist：

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

推荐后续按需加入 `microsoft/autogen`、`deepset-ai/haystack` 等 Agent / RAG 仓库。普通重复执行 `init` 不会覆盖你的 watchlist；`init --force` 会恢复默认列表。

推荐优先配置两个东西：GitHub Token 和 LLM 服务。

#### GitHub Token（推荐）

没有 token 时，GitHub API 访问额度很低；配置 token 后，更适合每天扫描多个仓库：

```bash
export GITHUB_TOKEN=your-github-token
opensense init --github-token-env GITHUB_TOKEN
```

#### LLM 服务（可选但推荐）

没有 LLM key 也能用，OpenSense 会退回确定性规则评分。配置 LLM 后，`issue --plan` 可以生成更好的摘要、风险判断和 PR 前计划。

```bash
export OPENSENSE_LLM_API_KEY=your-api-key
export OPENSENSE_LLM_BASE_URL=https://api.openai.com/v1
export OPENSENSE_LLM_MODEL=gpt-5.5

opensense init \
  --llm-api-key-env OPENSENSE_LLM_API_KEY \
  --llm-base-url-env OPENSENSE_LLM_BASE_URL \
  --llm-model-env OPENSENSE_LLM_MODEL
```

配置文件只保存环境变量名，不保存原始 API key。LLM 配置同时会被 `daily` 和 `issue --plan` 使用。`daily` 更偏“帮你找”，`issue --plan` 更偏“帮你规划一个已经选中的 issue”。

### 2. 关注仓库和技术栈

```bash
opensense watch repo add vllm-project/vllm
opensense watch skill add python
```

OpenSense 采用 watchlist-first 的方式。它默认从你主动关注的仓库和匹配你贡献优势的技术栈出发，而不是一开始就搜索整个互联网。

### 3. 获取每日候选

```bash
opensense daily
```

`daily` 会扫描已关注仓库，并返回一份短候选列表。已关注的技术栈会对匹配 issue 产生轻量加分，例如 `python`、`llm`、`cli`、`tests` 可以把更适合你的任务排到更靠前的位置，但它不会成为唯一评分规则。

常用筛选参数：

```bash
opensense daily --min-stars 500 --updated-days 14 --max-comments 10 --limit 5
```

每条推荐会说明：

- 总分
- 可能的贡献类型
- 为什么看起来适合入手
- 建议执行的下一条命令

示例输出：

```text
Daily PR candidates

#  Issue                    Score  Type      Why                         Next
1  vllm-project/vllm#12345  82     bug fix   good first issue label      opensense issue vllm-project/vllm#12345
```

### 4. 分析并规划单个 issue

```bash
opensense issue vllm-project/vllm#12345
opensense issue vllm-project/vllm#12345 --plan
```

### 5. 本地 PR 尝试闭环

```bash
opensense pack https://github.com/vllm-project/vllm/issues/12345
opensense patch https://github.com/vllm-project/vllm/issues/12345 --dry-run
opensense propose https://github.com/vllm-project/vllm/issues/12345
opensense sandbox create https://github.com/vllm-project/vllm/issues/12345
opensense agent handoff https://github.com/vllm-project/vllm/issues/12345
opensense agent apply https://github.com/vllm-project/vllm/issues/12345 -- <agent command>
opensense test run https://github.com/vllm-project/vllm/issues/12345 -- <test command>
opensense pr draft https://github.com/vllm-project/vllm/issues/12345
opensense agent status https://github.com/vllm-project/vllm/issues/12345
opensense agent status https://github.com/vllm-project/vllm/issues/12345 --json
opensense attempt list
opensense attempt open https://github.com/vllm-project/vllm/issues/12345
```

`pack` 会在 `.opensense/packs/<owner>__<repo>/<issue-number>/` 下写入上下文包；`patch --dry-run` 只判断是否适合继续，不修改源码；`propose` 写出 `patch-proposal.md`；`sandbox create` 显式创建本地 git worktree；`agent handoff` 生成给编码 agent 的任务单；`agent apply` 只在 sandbox worktree 内运行你显式传入的命令，并记录 `agent-apply.json`、`agent-output.log`、`diff.patch`、`diffstat.txt`。

`test run` 记录真实测试命令、退出码和日志；`pr draft` 基于 agent apply、diff 和 test evidence 生成本地 PR 草稿；`agent status` 则把当前 issue 的本地尝试状态汇总成一个表格，并提示下一步该做什么。

如果你想把 OpenSense 接到 MCP、Skill 或 Web UI，优先使用 `agent status --json` 和 `attempt list --json`。`attempt open` 只展示本地 artifact 路径，不会打开 GitHub 或发起远端写操作。

这一整条链路默认都不 commit、不 push、不打开 PR、不评论 GitHub。OpenSense 负责把上下文、执行记录和 PR 草稿准备好，真正是否开 PR 仍由你人工判断。

### Agent / Skill 用法

OpenSense 很适合被打包成 Agent Skill：Skill 不需要重新实现 GitHub 搜索或打分逻辑，只需要把这条安全流程固定下来。

```text
daily -> issue --plan -> pack -> patch --dry-run -> propose
      -> sandbox create -> agent handoff -> agent apply
      -> test run -> pr draft -> agent status
```

建议 Skill 遵守三条边界：

- 先用 `daily` 和 `issue --plan` 做判断，再进入本地 PR 尝试。
- `agent apply` 只在 OpenSense 创建的 sandbox worktree 里执行。
- `pr draft` 只生成本地草稿，不自动 commit、push、开 PR 或评论 GitHub。

For agent clients, OpenSense also provides a read-only MCP entrypoint:

```bash
opensense-mcp
```

The MCP surface exposes `get_watchlist`, `read_pack`, `patch_dry_run`, `get_attempt_status`, `read_pr_draft`, and `read_agent_handoff`. It reads existing local state and pack artifacts only; it does not create PRs, comments, commits, branches, or source-code changes.

`issue` 会回答：

- 这个 issue 在说什么？
- 它更像 bug fix、tests、docs，还是 feature？
- 它是否适合做成一个小 PR？
- 哪些确定性信号说明它值得尝试？
- 写代码前应该先检查哪些规则风险？

`issue --plan` 会把一个候选 issue 转成 PR 前检查清单：

- 问题摘要
- 可能的贡献类型
- 优先阅读的文件或模块
- 建议实现路径
- 测试与验证清单
- 是否应该在编码前先留言确认
- PR 标题和正文草稿轮廓

### 6. 评估仓库

```bash
opensense repo vllm-project/vllm --skills python,llm
```

`repo` 会在你投入大量时间前，先检查仓库层面的轻量信号：

- 仓库 star 数
- 最近合并的 PR
- open PR 积压情况
- stale PR 比例
- 外部贡献者 PR 合并情况
- 仓库语言和你的技能是否重合

## 选择标准

OpenSense 不会只因为一个 issue 带着 `good first issue` 标签，就把它排到前面。真正值得动手的任务，通常还有一些更实际的信号：

- 问题描述比较清楚，至少知道从哪里开始复现或验证
- 改动范围看起来可控，能收敛成一个目标明确的 PR
- 最近还有维护者或贡献者参与讨论，不像已经被遗忘
- 暂时没人认领，也没有正在处理同一问题的关联 PR
- 更接近 bug fix、补测试、修 CI、typing、文档示例或小范围行为修正

有些 issue 看上去很有意思，但不一定适合今天开始做。遇到下面这些情况，OpenSense 会先把它们往后放：

- 讨论持续了很久，维护者仍没有明确想要的方案
- 已经有人在处理，或者现有 PR 基本覆盖了问题
- 表面是小修复，实际可能牵动大量架构和兼容性设计
- 必须依赖内部数据、特殊硬件或很难搭建的 benchmark 才能验证
- issue 描述太少，连问题是否还能复现都无法确认

## MVP 范围

OpenSense v1 聚焦开源贡献的筛选和规划。

当前已经支持：

- 维护 GitHub 仓库和个人技术栈的本地 watchlist
- 初始化 `.opensense/` 本地状态
- 通过 `init --check` 检查本地配置和可选环境变量
- 使用 GitHub API 扫描已关注仓库的 open issue
- 使用确定性规则对候选 issue 排序
- 可选使用 LLM 做更深入的分析和 PR 前计划
- 在用户开始写代码前生成 PR 前计划
- 在深入投入 PR 前做轻量仓库信号检查

当前默认不会：

- 修改主工作区源码
- commit / push
- 评论 issue / PR
- 创建 GitHub PR
- 声称未运行、失败、陈旧或不一致的测试已经通过

显式允许：

- `sandbox create` 创建本地 worktree 和分支
- `agent apply` 在 sandbox 内运行用户给出的命令并捕获 diff
- `test run` 运行用户给出的测试命令并记录 exit code
- `pr draft` 生成本地 PR 草稿

仍然禁止：

- obvious `git push` / `git commit` / `gh pr create` / `gh issue comment`
- shell wrapper 形式的 agent apply
- 泄露 secret-like 文本
- 把未验证证据写成已验证事实

## 架构

OpenSense 当前保持轻量，并按职责拆分 CLI、领域逻辑、外部服务与本地存储：

```text
src/opensense/
├── cli.py                      # 注册 CLI 命令并串联完整工作流
├── config.py                   # 初始化和读取 .opensense 本地配置
├── doctor.py                   # 检查配置文件、环境变量和状态目录
├── models.py                   # 定义 issue、评分和仓库信号数据模型
│
├── github/                     # GitHub 数据访问层
│   ├── client.py               # GitHub REST API 基础客户端
│   ├── issues.py               # 获取并转换 GitHub open issue
│   └── radar.py                # 收集仓库 PR、issue、语言等信号
│
├── core/                       # 排序、评分、规划与本地 PR 尝试逻辑
│   ├── pack.py                 # 生成 issue 上下文包和安全 manifest
│   ├── proposal.py             # 从 pack 生成 patch-proposal.md
│   ├── sandbox.py              # 创建和读取隔离 git worktree 元数据
│   ├── agent_workflow.py       # agent handoff/apply/status 的本地证据链
│   ├── command_safety.py       # 阻断明显远端写入和 shell wrapper 命令
│   ├── test_capture.py         # 捕获测试命令、退出码和日志
│   ├── pr_draft.py             # 根据 apply/test/diff 生成本地 PR 草稿
│   ├── radar.py                # 根据仓库信号计算贡献友好度
│   ├── scoring.py              # 使用确定性规则评估单个 issue
│   ├── ranking.py              # 结合技术栈匹配对候选 issue 排序
│   └── planner.py              # 生成规则或 LLM 辅助的 PR 前计划
│
├── mcp/                        # 只读 MCP 入口
│   └── server.py               # 暴露 watchlist、read_pack、patch_dry_run
│
├── llm/                        # 可选 LLM 能力
│   └── client.py               # 调用 OpenAI 兼容的 LLM 服务
│
└── storage/                    # 本地状态持久化
    ├── watchlist.py            # 读写仓库和技术栈 watchlist
    └── packs.py                # 管理 .opensense/packs 下的 artifact 路径和校验
```

当前实现使用 Typer/Rich CLI、GitHub API client、TOML 本地状态、确定性评分，以及可选的 LLM 辅助规划。

## 常见问题

### 可以通过 pip 安装吗？

可以。OpenSense 已经使用标准 `pyproject.toml` 和 `src/` 包结构，并配置了 `opensense` 命令行入口。

不过 PyPI 上的 `opensense` 名称已经被其他项目占用，因此本项目使用 `opensense-vp` 作为发布包名，同时保持安装后的命令名称不变：

```bash
pip install opensense-vp
opensense init
opensense daily
```

`opensense-vp` 已经发布到 PyPI，可以直接安装使用：

```bash
pip install opensense-vp
opensense --help
```

当前版本已通过 GitHub Actions 发布，并做过 PyPI 安装验证。后续每次发布都需要先提升版本号，再创建对应 Git tag 和 Release。

### 必须配置 GitHub Token 吗？

不是必须，但强烈推荐。没有 token 时 GitHub API 的访问额度较低，扫描多个默认仓库时更容易触发限流。

### 必须配置 LLM 吗？

不需要。没有 LLM 时，OpenSense 仍然可以使用确定性规则完成候选筛选和排序，并在 `daily` 里提示 LLM 分析被跳过；配置 LLM 后，`daily` 会从更大的候选池里辅助寻找更值得动手的 issue，`issue --plan` 会提供更深入的摘要、风险判断和 PR 前计划。

### 默认 watchlist 可以修改吗？

可以。`opensense init` 会提供一份 Agent / RAG 默认列表，你可以使用 `watch repo add` 和 `watch skill add` 继续扩展。普通重复执行 `init` 不会覆盖已有列表，`init --force` 会恢复默认配置。

## 许可证

本项目采用 MIT License，详见 [LICENSE](LICENSE)。
