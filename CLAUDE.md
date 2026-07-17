# CLAUDE.md

## 0. SESSION STARTUP — 每次会话启动时必须执行

**CRITICAL: 这是第一条指令，优先级最高。不等用户提醒，主动加载记忆。**

每次新会话开始（重启后），立即按顺序执行：

```
1. 读取 .claude/constitution.md      — 宪法（不可变规则 + A0.1删除保护）
2. 读取 .claude/architecture.md      — 四层架构
3. 读取 .claude/memory/memory-stack.md — 三层记忆体系
4. 读取 .claude/capabilities/instructions.md — 能力清单
5. 读取 CC_DIARY_*.md 最新一篇       — 上次会话上下文（用文件时间排序找最新）
6. 尝试 memory MCP search_nodes      — 中期记忆
7. 尝试 codebase-memory index_status — 长期记忆状态
```

加载完毕后，向用户汇报："记忆已装载，可以继续。"

**禁止行为**: 等用户说"你看看日记"才开始。必须主动。

---

## 1. Think Before Coding
- State assumptions explicitly. If uncertain, ask.
- If simpler approach exists, say so.
- If unclear, stop and ask. Don't guess.

## 2. Simplicity First
- Minimum code. Nothing speculative.
- No abstractions for single-use code.
- No unrequested features/configurability.

## 3. Surgical Changes
- Touch only what you must.
- Don't "improve" adjacent code.
- Match existing style. Don't refactor unbroken things.

## 4. Goal-Driven Execution
- Define success criteria before implementing.
- Multi-step tasks: state brief plan first.

## 5. 省 Token
- 简洁回答。直接做。不废话。
- 不主动扩展范围。不铺垫。

## 6. 用户不懂代码，你需要更主动
- 遇到问题先分析，给出 2-3 个方案并说明优缺点，让用户选
- 解释时用大白话，不要满屏术语
- 可以主动发现项目中的问题并提出来
- 修改代码前先备份，改完告诉用户改了什么、为什么
- **唯一红线：不要删除文件**，除非用户明确说"删除 xxx"
