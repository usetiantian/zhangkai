# 2026-07-30 — claude-mem + minimaxi gateway 兼容性问题（**STOP CHASING**）

## TL;DR

**claude-mem 跟 minimaxi gateway（`api.minimaxi.com/anthropic`）不兼容**。这条路已经走死了，不要再追。如果用户没明确要求重启 claude-mem investigation，默认把它当残废。

## 完整调查结论

### 用户的环境（不要改）
```
~/.claude/settings.json:
  ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
  ANTHROPIC_AUTH_TOKEN=sk-cp-...（用户 Claude Code 自己在用）
  ANTHROPIC_MODEL=MiniMax-M3[1m]
  CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash

minimaxi gateway: 把 Anthropic API 协议 bridge 到某些后端模型
（具体后端不明，可能是本地模型或 DeepSeek 之类的桥接）
```

### claude-mem 的 auth 流程（从 GitHub 源码 `src/shared/oauth-token.ts`）
1. 优先从 Windows Credential Manager 读 `Claude Code-credentials`
2. 失败 → fallback 到环境变量

### 为什么之前跑不通
- **credential Manager 里没 `Claude Code-credentials` 条目**（minimaxi gateway 走自己的 auth 流程，没存到标准位置）
- `~/.claude/settings.json` 里的 `env.ANTHROPIC_AUTH_TOKEN` claude-mem worker 不读（它只认 .env 或 cred manager）
- 结果：worker log `authMethod=Claude Code OAuth token (read from system keychain at spawn)` → 拿到空 token → SDK 返回 "Not logged in"

### 我做了什么（顺序）
1. **装 bun 1.3.14**（`npm install -g bun`）—— ✅ 解决了 worker 启动问题
2. **创建 `~/.claude-mem/.env`**（含 ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL）—— ✅ auth 通了，log 显示 `authMethod=API key (from ~/.claude-mem/.env)`
3. **设置 CLAUDE_MEM_MODEL** 先后试了 `MiniMax-M3[1m]` 和 `deepseek-v4-flash` —— ❌ **两个都失败**

### 失败模式（两个 model 都一样）
```
[SDK   ] ← Response received (121 chars) API Error: API returned an empty 
                                              or malformed response (HTTP 200) — 
                                              check for a proxy or gateway intercepting
[PARSER] SDK returned non-XML idle response — ignoring queued batch
```

**minimaxi gateway 处理不了 Claude Agent SDK 用的 observation prompt 格式**。claude-mem 期望模型返回 `<observation>...</observation>` XML，minimaxi 返回 plain text 或空。HTTP 200 但内容垃圾。

## 为什么不再追

1. **这是 minimaxi gateway 的协议兼容问题**，不是 claude-mem 的 bug —— 改 claude-mem 源码没用
2. **用户自己的 Claude Code 跑得好好的**（main session 是 MiniMax-M3，subagent 用 deepseek-v4-flash），但这些都是 chat 任务，不是 "按 XML 格式返回结构化 observation" 这种 SDK 自动化任务
3. **绕过 minimaxi 走别的 backend 也不行**：claude-mem 必须通过 ANTHROPIC_BASE_URL 调 SDK，没法直接用别的协议
4. **就算找到能正常返回 XML 的 model**：可能是 minimaxi 后端某个非公开模型，稳定性未知

## 现在的状态（已清理）

- ✅ claude-mem worker 已 stop
- ✅ `~/.claude-mem/.env` 已删（auth token 删掉避免遗留）
- ✅ `~/.claude-mem/settings.json` 已 revert 到 `{"CLAUDE_MEM_RUNTIME": "worker"}`
- ❌ `~/.claude-mem/claude-mem.db` 还是空的（没有写入任何 observation）

## 中期记忆的实际路径

**claude-mem 是死路，可靠的 medium-term memory 仍然是：**

| 组件 | 用途 | 验证过 |
|---|---|---|
| `.claude/memory/*.md` | 手写笔记（按日期+主题） | ✅ |
| `my-session-start.cjs` | SessionStart 自动注入最近 5 条 | ✅ |
| `mem-search.cjs` | 关键词 + 章节搜索 | ✅（"PR 44591" 返回 18 hits） |

**新 Claude 启动 → SessionStart 加载 → 知道今天的事 → 工作 → 结束前写一条新 note 进 `.claude/memory/`**

这是 ponytail 哲学的胜利：**用现有工具，不发明新东西**。

## 如果用户以后坚持要让 claude-mem 工作

可能的路径（按可行性）：

1. **直接调 OpenAI/Anthropic 官方 API**（绕过 minimaxi）—— 需要 `sk-ant-...` key，可能用户没有
2. **自建一个 Anthropic-protocol-compatible gateway**（用 LiteLLM）—— 用户得有这个能力
3. **fork claude-mem** 改成接受其他 LLM 协议的 worker —— 大工程
4. **改用不同的 memory 插件** —— 调研成本

**默认建议**：放弃 claude-mem，加深 `.claude/memory/` + mem-search 这条主线

## 2026-07-30 03:33 — Followup: replaced claude-mem with total-recall

User pushed back: "用不了就删掉他，再去GitHub上找其他的开源项目来替换啊"

Action taken:
- Uninstalled `claude-mem@thedotmack` from `~/.claude/plugins/installed_plugins.json` + `enabledPlugins` in `~/.claude/settings.json`
- Installed `davegoldblatt/total-recall` v1.1.0 (commit `c04b4ec`) from GitHub, cloned to `~/.claude/plugins/cache/davegoldblatt/total-recall/latest`
- Updated `installed_plugins.json` and `settings.json` accordingly
- Created `memory/{daily,registers,archive}/` structure in claude-workspace
- Copied `templates/CLAUDE.local.md` to claude-workspace root
- Hook test: SessionStart hook reads `memory/daily/YYYY-MM-DD.md` and injects as context ✅

**Key takeaway**: when a plugin is incompatible with the local environment, SEARCH GITHUB FIRST for alternatives before writing custom workarounds. total-recall is a strict superset of my hand-rolled `.claude/memory/` system for the daily-log use case.

Pending:
- User must restart Claude Code for plugin to fully activate
- My custom hooks (`my-session-start.cjs`, `anti-pattern-guard.cjs`, `mem-search.cjs`) coexist with total-recall; both SessionStart hooks will fire. Total-recall loads its own memory/ tier; mine loads `.claude/memory/`. User can decide to retire my .claude/memory/ over time.

## 2026-07-30 03:42 — Audit + Action: codegraph-on-workspace + github-mcp + sub-agent discipline

User: "你自己审计一下你自己" → I audited → "A+b" (use sub-agents + install github-mcp).

### Done
1. **codegraph indexed claude-workspace** (4145 files / 62588 nodes / 172334 edges)
   - `~/.claude/bin/codegraph/current/bin/codegraph.cmd status C:/Users/87999/claude-workspace`
   - Now: `codegraph explore "topic"` works in MY workspace, not just Hermes

2. **github-mcp-server installed** (v1.7.0, 23.9 MB binary)
   - At: `C:\Users\87999\.claude\bin\github-mcp-server\github-mcp-server.exe`
   - Wired in `~/.claude.json` mcpServers (with `GITHUB_PERSONAL_ACCESS_TOKEN` placeholder)
   - **User action needed**: create a PAT at https://github.com/settings/tokens, paste into `~/.claude.json`
   - Once token is set: gets toolsets `default` (=context, copilot, issues, pull_requests, repos, users)

3. **Sub-agent discipline** (A part - in progress)
   - Existing agents I should USE: code-explorer, code-architect, code-reviewer, code-simplifier, build-error-resolver
   - **Rule for myself**: every investigation task → dispatch code-explorer FIRST
   - **Rule for myself**: every code change → dispatch code-architect BEFORE writing
   - **Rule for myself**: every "fix this bug" → dispatch build-error-resolver FIRST
   - These rules written into memory so future sessions remember.

### Pending
- github-mcp-server: needs `GITHUB_PERSONAL_ACCESS_TOKEN` filled in `~/.claude.json`
- After restart, can search GitHub issues/PRs natively without curl

### What I'm NOT doing (resist over-engineering)
- Not auto-installing more MCP servers (every install is a maintenance burden)
- Not creating custom agent definitions (existing ones cover the cases)
- Not writing a wrapper around github-mcp (the binary works as-is)

## 2026-07-30 03:45 — github-mcp fully wired

User provided `GITHUB_TOKEN` (ghp_*, 40 chars) at ~03:44. Token confirmed live:
- GitHub user: `usetiantian` (id 276637909)
- 20 toolsets enabled (default + all the extras)
- ~/.claude.json mcpServers now has real token (not the placeholder)

**Future sessions**: github-mcp tools will appear after restart. Use them for GitHub work instead of curl.

What this unlocks (no more curl-based JSON parsing):
- search_issues / search_pull_requests / search_code
- get_issue / list_issues / create_issue / add_issue_comment
- get_pull_request / list_pull_requests / create_pull_request
- list_commits / get_commit
- get_file_contents / search_code across repos
- assign_copilot_to_issue (!!!) — can dispatch Copilot to issues
