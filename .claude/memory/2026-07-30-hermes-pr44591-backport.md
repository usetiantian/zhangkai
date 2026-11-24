# 2026-07-30 — Hermes PR #44591 本地 backport

## TL;DR
用户的 Hermes 安装 (`C:\Users\87999\AppData\Local\hermes\hermes-agent\`) 有上游已知 bug：update 流程 build 失败时仍报 "Update complete!" 并 exit 0。已经在本地 backport 了 PR #44591 的修复（5 处改动 + 1 个测试类）。下次 `hermes update` 之前先确认 patch 还在。

## 背景

**Issue [#44580](https://github.com/NousResearch/hermes-agent/issues/44580)**: `hermes update reports success when desktop rebuild silently fails`
**PR [#44591](https://github.com/NousResearch/hermes-agent/pull/44591)**: `fix(cli): propagate desktop build failure to hermes update exit code`
- Upstream 状态 (2026-07-30): **open, 未 merge**
- 用户的 local main.py (`cbecd72`) 和 upstream `main` (`9102d4a`) 都有这个 bug

## 触发场景
- Electron CDN 拉不到（国内常见），`hermes desktop --build-only` 失败
- `npm` 不在 PATH
- 任一 build 阶段（assert-dist-built / stage-native-deps / electron-builder stage / rcedit）失败
- 失败后 Hermes.exe 启动时缺 `icudtl.dat` 等 → 报 `Invalid file descriptor to ICU data received` 一秒闪退

## 本地 backport 内容

### 改了 5 个地方 in `hermes_cli/main.py`

| # | 行号 (post-patch) | 改动 |
|---|---|---|
| 1 | 12786 | `has_desktop_app = ...` 之前加 `_desktop_build_failed = False` |
| 2 | 12810 | build 失败时 `_desktop_build_failed = True` + 把 "non-fatal" 去掉 |
| 3 | 13164-13168 | "✓ Update complete!" 改成条件分支（失败时打印 loud banner） |
| 4 | 13275 | `.update_exit_code` 写 "1" 代替 "0"（gateway mode） |
| 5 | 14007-14009 | 末尾 `if _desktop_build_failed: sys.exit(1)` |

**注意**：第 3 处保留了本地 tail/log 输出（PR upstream 版本简化掉了），更有 debug 价值。

### 加了测试 in `tests/hermes_cli/test_cmd_update.py`
- 新类 `TestUpdateDesktopBuildFailure`，3 个 test：
  - `test_desktop_build_failure_prints_loud_banner_and_exits_1` — 失败时 exit 1 + loud banner
  - `test_desktop_build_success_prints_update_complete` — 成功时正常
  - `test_no_desktop_app_skips_build_and_exits_cleanly` — 没装桌面时跳过
- **测试都过了**（2026-07-30 验证）

## 关键文件路径

```
C:\Users\87999\AppData\Local\hermes\hermes-agent\hermes_cli\main.py
C:\Users\87999\AppData\Local\hermes\hermes-agent\hermes_cli\main.py.pr44591.bak   # 备份（760KB，原始版本）
C:\Users\87999\AppData\Local\hermes\hermes-agent\tests\hermes_cli\test_cmd_update.py
```

## 验证 patch 还在

```bash
grep -c "_desktop_build_failed" "C:/Users/87999/AppData/Local/hermes/hermes-agent/hermes_cli/main.py"
# 应该 ≥ 5

cd "C:/Users/87999/AppData/Local/hermes/hermes-agent" && \
  "C:/Users/87999/AppData/Local/hermes/hermes-agent/.venv/Scripts/python.exe" \
  -m pytest tests/hermes_cli/test_cmd_update.py::TestUpdateDesktopBuildFailure -v
# 应该 3 passed
```

---

## 2026-08-05 增量 — 经 hermes update 到 v0.20.0 后，关键变化

- upstream 把 `_cmd_update_impl` 从 `hermes_cli/main.py` 提取到了 `hermes_cli/update_cmd.py`（"main.py decomposition" mechanical move）。re-export 仍然在 `main.py`，所以 patch target 改了文件但 pattern 不变
- **patch 现在的位置**：4 处都在 `hermes_cli/update_cmd.py`，原来的 5 处缩到 4 处（line 4204, 4252, 4604, 5437），原文件 `hermes_cli/main.py` 不再承担这块逻辑
- 旧的 `hermes_cli/main.py.pr44591.bak`（760KB）是 v0.19.0 时代的备份，现在已经过期（pre-refactor 的 main.py），**别再 cp 它回去当回滚点** — 那会把 repo 退回 refactor 前的状态

### npm 版本陷阱（今天踩了）

upstream `engines.npm` 是 `"<11.10.0 || >=11.17.0"`。Windows 系统 Node.js 24.x 默认装的是 npm 11.16.0，正好在排除区间。`hermes update` 走到 `npm install` 时 EBADENGINE 退出，但**update 主流程继续往下走**（pip/deps/desktop rebuild 都失败但 update 仍报 "✓ Code updated"）—— PR #44591 patch 让它应该 exit 1，但如果 patch 没回来就会"假完成"。

**修复**：
```bash
npm install -g npm@11.18.0  # ≥11.17.0 就过
# 或者用 Hermes-managed Node（让脚本自动隔离）
```

### 今天的更新流程（验证过 OK）

1. 检查有没有 Hermes 进程在跑（`Get-Process | Where Path -match hermes-agent`）。有就先 stop（gateway `Stop-Process -Id <pid> -Force`，注意 anti-pattern-guard 不让硬编码大 PID — 用脚本或者 query-then-stop）
2. 备份当前 local patches：`git diff HEAD > /tmp/pre-update-local-patch.diff`
3. `./hermes update --yes --backup` —— 会自动 stash + reset --hard 到 origin/main + 应用 stash（应用失败的 stash 保留在 stash list 里 `stash@{0}`）
4. 检查 npm 版本（如上），必要时升级
5. 在 `hermes_cli/update_cmd.py` 重新 apply PR #44591 backport（4 处）
6. 重跑 `./hermes update`（或单独 `.venv/Scripts/python.exe -m hermes_cli.main desktop --build-only --force-build`）—— 完成 npm install + desktop rebuild
7. `pytest TestUpdateDesktopBuildFailure -v` —— 3/3 应过

### 备份

- 472MB pre-update zip 在 `~/AppData/Local/hermes/backups/pre-update-2026-08-05-141802.zip`，30 天后才清理
- 完整恢复：`hermes import <path>`
- stash `d002d18eb77a422e6d4333d0b2f08e3a56a3dd02` 还在 (`git stash list` 看到)，可以 `git stash show` 看 diff 再决定要不要 drop

### Docker / Nix 用户呢

- `--check` 提示 Docker 用户用 `docker pull`，Nix 用户用对应命令 — script 自己会 bail 友好信息

## Revert（如需要）

```bash
cp "C:/Users/87999/AppData/Local/hermes/hermes-agent/hermes_cli/main.py.pr44591.bak" \
   "C:/Users/87999/AppData/Local/hermes/hermes-agent/hermes_cli/main.py"
# 然后从 test_cmd_update.py 末尾手动删 TestUpdateDesktopBuildFailure 类
```

## Upstream 同步策略

当 PR #44591 merge 后，`hermes update` 会拉新代码并**和我本地的 backport 冲突**（5 处改动重叠）。处理顺序：
1. 先 `cp main.py.pr44591.bak main.py` 撤掉 patch
2. 再 `hermes update`
3. 验证 patch 已经在 upstream code 里（grep 上面那条）

如果冲突报错，git 3-way merge 通常能搞定；不行就手动 re-apply 5 处。

## 关联 incident

- 今天 0:53 的 `win-unpacked` 重建就触发了这个 bug：build 静默失败 → user 看到 "Update complete!" → 重启 Hermes.exe → 闪退
- 当时的 workaround：我手动从 `node_modules/electron/dist/` 补了 9 个缺失文件（`icudtl.dat` 等）到 `release/win-unpacked/`
- 现在 patch 在了，下次 `hermes update` 失败时 user 会立刻看到红字

## 别再做的事

❌ 不要自己写 `assert-electron-runtime.mjs`（之前我想过这方案，被用户骂了）
✅ upstream 已经有完整的 self-heal 系统（`_ensure_desktop_exe_launchable` + cache purge + mirror fallback + rollback），我的层应该在 `hermes update` 流程里，而不是 build 端

❌ 不要手动逐个 cp 文件补 `release/win-unpacked/` 里缺失的文件（icudtl.dat / locales / *.pak 等）
✅ 正确做法是 `hermes desktop --force-build` —— `before-pack.mjs` 的 `cleanStaleAppOutDir()` 会整棵砍掉 `win-unpacked` 重打。手动补文件会留下不一致状态（比如 asar header 标 dist/** 为 unpacked 但 `.unpacked/dist/` 实际不存在），引发更难诊断的连锁错误（比如 7/30 第二次报的 `electron-main.mjs not found`）

❌ 不要在 build 流程跑的时候用 `npm install` 起新进程、用 PowerShell 弹窗、或试图往 `app.asar.unpacked/` 里手工塞文件
✅ 让 `hermes desktop --force-build` 一条路走完；任何阻塞时停下问用户

## 工具配置

- **CodeGraph** (colbymchenry/codegraph, 63k stars, Rust 内核) 已通过 `npm i -g @colbymchenry/codegraph` 装好
  - 路径：`C:\Users\87999\AppData\Local\codegraph\current\bin\codegraph.cmd`
  - 已对 Hermes 项目执行 `codegraph init`（在 `apps/desktop/release/` 旁建 `.codegraph/`）
  - 下次再问 Hermes 内部代码问题，先用 codegraph 查 graph 再动手，不要再用 grep + Read 凑
- **Hermes 桌面端** PR #44591 backport 之后，下次 build 失败会明显报错。`hermes desktop --force-build` 完整路径已验证（2026-07-30 2:24:56 重启 gateway → 2:26:16 Hermes.exe 主进程起来）

## 自建持久化基础设施（关键！下次启动自动生效）

我手写了两个**自包含 Node 钩子**（无 npm 依赖、无外部插件），registered 进 `.claude/hooks/hooks.json`：

### 1. `my-session-start.cjs` (SessionStart)
- 路径：`C:\Users\87999\claude-workspace\.claude\hooks\my-session-start.cjs`
- 功能：会话启动时**自动读 `.claude/memory/*.md` 最近 6 个文件**，渲染前 30 行 preview，emit 到 stdout → Claude Code 自动 inject 到新会话 context
- 验证过：跑了一下，5 个 note 都加载了
- hooks.json id: `session:start:memory-loader`

### 2. `anti-pattern-guard.cjs` (PreToolUse on Edit|Write|MultiEdit|Bash) — **PROJECT-AGNOSTIC**
- 路径：`C:\Users\87999\claude-workspace\.claude\hooks\anti-pattern-guard.cjs`
- **架构原则**：这个 hook 是 generic 的，**不绑定任何具体项目**（Hermes、electron-builder、npm 都不在 hook 代码里出现）
- 功能：硬拦截三个**结构性**反模式（任何项目都会踩）：
  - **Edit/Write/MultiEdit** 到 `release/<plat>-unpacked/` 或 `app.asar.unpacked/`（任何 build tool 的产物）
  - **Bash cp/Copy-Item/robocopy/xcopy** 进 `release/<plat>-unpacked/`
  - **Bash Stop-Process** 硬编码大 PID（任何进程都会撞这个坑）
- 拦截方式：emit JSON `{permissionDecision: deny, permissionDecisionReason: ...}`，Claude Code 自动拒绝该 tool call 并把 reason 给模型
- **Per-project 定制**：如果某个项目想用自己的 redirect 文本，**复制** `anti-pattern-redirects.EXAMPLE.json` 为 `anti-pattern-redirects.json`，按需修改。**不创建就不生效**，默认走 generic
- 测试全过（10 个 case + override loader 验证）
- hooks.json id: `pre:anti-pattern-guard`

### 为什么 anti-pattern-guard 不绑定 Hermes？
- workspace-level 基础设施**不应该耦合**任何具体项目
- 这套 hook 在 Hermes 之外的 Electron 项目里也能直接 ship，零修改
- Hermes-specific 的 redirect（指向 `hermes desktop --force-build`、stop_hermes.ps1 等）只在 `.claude/hooks/anti-pattern-redirects.json` 创建后才生效 —— **opt-in**，不影响其他项目
- 你之前提的"我和 Hermes 应该没联系"原则：默认 generic，Hermes 是个可选的 override

### 为什么自包含而不是用插件？
- ECC 插件 (`~/.claude/plugins/ecc/`) 实际**未安装**，hooks.json 里那堆引用 ECC 的 entry 全是**死配置**，silent fail
- claude-mem 插件（实际装着的）有 MCP 工具但 worker API 今天 fetch failed（不可靠）
- 自包含 Node 脚本 = 零依赖、永远跑得起来，不会因为某个 npm 包升级坏掉

### 下次会话会发生什么
1. 启动 → SessionStart hook 触发 → `.claude/memory/` 5 个最近 note 自动注入 → **新 Claude 一开始就知道今天的教训**
2. 我想 Edit `release/win-unpacked/Hermes.exe` → PreToolUse hook 触发 → **直接拒绝 + 给出正确命令**（`hermes desktop --force-build`）
3. 我想手动 cp `icudtl.dat` 进 release → **直接拒绝**
4. 我想 Stop-Process -Id 26976 → **直接拒绝 + 指向现有 stop_hermes.ps1**

### 如果哪天 hooks.json 被覆盖
最坏情况：hooks 失效，但 `.claude/memory/` 还在，session-start 没法 auto-load，新 Claude 又得重学一遍。所以：
- **记忆笔记是新 Claude 的最后一道防线**（永远别删 `.claude/memory/2026-07-30-hermes-pr44591-backport.md`）
- hooks 是**第一道防线**（拦截 + 重定向）
- 两者**双保险**

### 测试 hooks 是否还在生效
```bash
# 测 session-start loader:
node "C:/Users/87999/claude-workspace/.claude/hooks/my-session-start.cjs" < /dev/null | head -20

# 测 anti-pattern guard:
echo '{"tool_name":"Edit","tool_input":{"file_path":"C:/foo/release/win-unpacked/Hermes.exe"}}' | node "C:/Users/87999/claude-workspace/.claude/hooks/anti-pattern-guard.cjs"
# 应该输出 {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",...}}
```
