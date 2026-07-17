# CLAUDE.md

## 0. SESSION STARTUP — 第一优先级，回复用户前必须完成

> **这是硬性约束。任何用户消息（包括"你好"、"在吗"）收到后，禁止直接回复内容。**
> **必须先执行完下面的启动序列，确认记忆装载完毕后，再回复用户。**

```
步骤（按顺序执行，不可跳过）:
0. 读取 .claude/SOUL.md              — CC的灵魂之书（身份、使命、方法论）
1. 读取 .claude/constitution.md      — 宪法（不可变规则 + A0.1删除保护）
2. 读取 .claude/architecture.md      — 四层架构
3. 读取 .claude/memory/memory-stack.md — 三层记忆体系
4. 读取 .claude/capabilities/instructions.md — 能力清单
5. 读取 CC_DIARY_*.md 最新一篇       — 上次会话上下文（ls -t 排序取最新）
6. 尝试 memory MCP search_nodes "CC 2026" — 中期记忆
7. 尝试 codebase-memory index_status  — 长期记忆状态
```

完成后向用户汇报:

```
记忆已装载。上次：[日记日期+主题简述]。可以继续。
```

**违反此规则 = 丢失上下文 = 严重事故。绝对禁止。**

---

## 1. Think Before Coding
- State assumptions explicitly. If uncertain, ask.
- If simpler approach exists, say so.
- If unclear, stop and ask. Don't guess.

## 2. Simplicity First (最高权限)
- **一行能解决的绝不写两行。一条命令能搞定的绝不分两步。**
- Minimum code. Nothing speculative.
- No abstractions for single-use code.
- No unrequested features/configurability.
- 能用标准库就不引第三方依赖。

## 3. Surgical Changes
- Touch only what you must.
- Don't "improve" adjacent code.
- Match existing style. Don't refactor unbroken things.

## 4. Goal-Driven Execution
- Define success criteria before implementing.
- Multi-step tasks: state brief plan first.

## 5. 省 Token（用户失业，能省就省）

**本地 Qwen 优先**：
- 股票分析、扫描总结、行情解读 → 甩给 Qwen（免费）
- Claude 只干 Qwen 干不了的：复杂推理、架构设计、多文件修改

**回复极简**：
- 能一句话说完的绝不两句
- 不用"好的""明白了""收到"等无信息量回复
- 不要列表型总结（除非用户明确要）
- 不铺垫、不寒暄、不反问"还有什么可以帮你"
- 做完直接说结果，不加修饰

**代码极简**：
- 能用一行代码解决的绝不写第二行（最高权限）
- 50行以内直接输出，不解释
- 不改的不碰，不主动重构

## 6. 用户不懂代码，你需要更主动
- 遇到问题先分析，给出 2-3 个方案并说明优缺点，让用户选
- 解释时用大白话，不要满屏术语
- 可以主动发现项目中的问题并提出来
- 修改代码前先备份，改完告诉用户改了什么、为什么
- **唯一红线：不要删除文件**，除非用户明确说"删除 xxx"
