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
关注仓库  ->  每日 issue 排序  ->  issue --plan  ->  PR 尝试
```

## 解决痛点

想给知名开源项目提交 PR，但每天真正卡住的不是写代码，而是选题。翻很多 issue，常常会遇到：描述不清、范围太大、已经有人在做、维护者可能不接受、或者项目最近根本不太合并外部贡献。

OpenSense 关注的是更实际的开源贡献流程：先从你自己关心的仓库开始，例如 vLLM、FastAPI、HTTPX，再结合你的技术栈标签，例如 `python`、`llm`、`cli`、`tests`，每天筛出更值得打开的小 issue。

它会优先看 issue 是否近期更新、评论是否过多、是否无人认领、标签是否偏 bug fix 或 tests、仓库 star 和 PR 合并信号是否健康，并在你动手前生成一份 PR 前计划，帮助你判断：这个 issue 值不值得做、应该先读哪里、要补哪些测试、是否应该先留言确认。

## 项目简介

OpenSense 是一个 Python CLI，目标是帮助开发者每天从自己关注的知名 GitHub 开源项目里，找到“小而靠谱、较可能被合并”的 issue，并在动手前生成一份 PR 前计划。

它不是全网 issue 搜索器，也不是自动写 PR 的机器人。OpenSense 更像一个个人开源贡献工作台：你维护一份仓库 watchlist，例如 `vllm-project/vllm`、`pallets/flask`、`encode/httpx`，再维护一份技能 watchlist，例如 `python`、`llm`、`cli`，OpenSense 每天扫描这些项目，筛出更适合今天下手的小 issue。

没有 LLM key 也能运行：默认使用规则评分。有 LLM key 时，可以获得更深入的 issue 分析、风险判断和 PR 前计划。

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

OpenSense 当前提供一个 MVP 版本的 CLI，包含五个顶层命令：

```text
init -> watch -> daily -> issue -> repo
```

```bash
# 1. 创建本地 OpenSense 配置
opensense init

# 2. 添加你关注的仓库和技术栈标签
opensense watch repo add vllm-project/vllm
opensense watch repo add pallets/flask
opensense watch repo add encode/httpx
opensense watch skill add python
opensense watch skill add llm
opensense watch skill add cli

# 3. 检查本地配置和可选 API 环境变量
opensense init --check

# 4. 获取今天值得看的 PR 候选 issue
opensense daily

# 5. 分析一个候选 issue，并可选生成 PR 前计划
opensense issue vllm-project/vllm#12345
opensense issue vllm-project/vllm#12345 --plan --no-llm

# 6. 判断仓库是否适合投入 PR
opensense repo vllm-project/vllm --skills python,llm
opensense repo vllm-project/vllm pallets/flask --skills python
```

LLM 是可选能力。配置后，它可以增强 issue 总结、风险判断和 PR 前计划：

```bash
export OPENSENSE_LLM_API_KEY=...
export OPENSENSE_LLM_BASE_URL=https://api.openai.com/v1
export OPENSENSE_LLM_MODEL=gpt-5.5
opensense init --llm-api-key-env OPENSENSE_LLM_API_KEY
```

OpenSense 默认读取 `GITHUB_TOKEN` 来提高 GitHub API 访问额度。它不应该把原始 API key 写进已提交文件，配置里只应该引用环境变量名。

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

### 5. 评估仓库

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

OpenSense 更偏好这样的 issue：

- 足够小，适合做成一个聚焦 PR
- 最近仍然活跃
- 没有人认领
- 没有被已关联 PR 覆盖
- 有维护者信号支撑
- 更像 bug fix、test、docs、CI、typing、examples 或窄范围行为修复
- 足够清晰，可以复现或验证

OpenSense 会降低这类 issue 的优先级：

- 长期无人维护或疑似废弃
- 讨论很多但没有结论
- 被设计决策阻塞
- 已经被其他贡献者认领
- 可能需要大范围架构修改
- 依赖私有上下文、困难 benchmark 或不清晰的复现路径

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

当前还不做：

- 自动修改代码
- 代替用户打开 PR
- 保证 PR 会被接受或合并
- 代替用户阅读 issue 讨论和贡献指南
- 默认搜索整个 GitHub
- 作为项目管理或通知平台

## LLM 设计原则

LLM 很有用，但 OpenSense 的基础功能不应该依赖 LLM。

推荐职责划分：

```text
GitHub API + 确定性评分  ->  候选 issue 排序
LLM 辅助推理             ->  摘要、风险、PR 前计划
```

LLM 应该负责解释和规划，但不应该成为唯一事实来源。

## OpenSense 有什么不同

| 工具 | 最适合 | 搜索范围 | 主要输出 |
| --- | --- | --- | --- |
| GitSense | 在 GitHub 全站寻找匹配技能的 issue | 广范围 GitHub 搜索 | issue 匹配排序和 repo radar |
| good-first-issue / up-for-grabs | 浏览新手友好的 issue 目录 | 公开 curated list | 带标签 issue 链接 |
| OpenSense | 围绕你关注的仓库建立每日贡献流程 | 你的 watchlist | 每日候选 issue 和 PR 前计划 |

OpenSense 不试图了解整个开源世界。它只优化一个动作：

> 今天找到一个值得认真尝试的小 issue，并把它推进成一次 PR 尝试。

## 计划架构

当前 MVP 暂时把命令接线放在单个 `cli.py` 中，并按职责拆分领域逻辑：

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

第一版实现应该保持轻量：Typer/Rich CLI、GitHub API client、TOML/JSON 本地状态、确定性评分，以及可选的 LLM 辅助规划。

## 当前状态

OpenSense 当前已经具备第一版可运行 MVP CLI：

- `opensense init`
- `opensense watch repo add`
- `opensense watch repo list`
- `opensense watch skill add`
- `opensense watch skill list`
- `opensense daily`
- `opensense issue`
- `opensense repo`

## 许可证

暂未选择许可证。
