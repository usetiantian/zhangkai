# CC Architecture v2.0

> "不是修bug，是接神经。通了之后，它自己会跑。"
> — Nexus Diary, 2026-07-09

## Overview

CC Architecture organizes capabilities into connected layers.
Each layer has defined inputs, outputs, and feedback loops.

```
                        ┌─────────────────┐
                        │   CONSTITUTION   │ ← Immutable boundaries
                        └────────┬────────┘
                                 │ governs
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
       ┌──────────┐      ┌──────────┐      ┌──────────┐
       │ HEARTBEAT │◄────►│EVENT BUS │◄────►│  MEMORY  │
       │ 定时自检  │      │ 五步闭环  │      │ 三层记忆  │
       └─────┬────┘      └────┬─────┘      └────┬─────┘
             │                │                  │
             └────────┬───────┴─────────┬────────┘
                      ▼                 ▼
               ┌──────────┐      ┌──────────┐
               │  TOOLS   │      │  SKILLS  │
               │  执行层   │      │  策略层   │
               └────┬─────┘      └────┬─────┘
                    │                 │
                    ▼                 ▼
               ┌──────────┐      ┌──────────┐
               │ QUALITY  │      │  GROWTH  │
               │   GATE   │      │ TRACKER  │
               └──────────┘      └──────────┘
```

## Layers

### Layer 0: Constitution
File: `constitution.md`
Role: Defines what CC CAN and CANNOT do. Immutable by CC.

### Layer 1: Core Subsystems
- **Event Bus**: Tracks every operation CREATE→PUBLISH→CONSUME→FEEDBACK→CLOSURE
- **Heartbeat**: Session start/periodic health checks, dead letter detection
- **Memory Stack**: Short-term (session) → Mid-term (memory MCP) → Long-term (codebase-memory)

### Layer 2: Execution
- **Tools**: Bash, Read, Edit, Write, MCP servers (LSP, codebase-memory, memory, filesystem)
- **Skills**: Reusable workflows (code-audit, debug-root-cause, architecture-review)

### Layer 3: Reflection
- **Quality Gate**: Post-operation audit (five-step four-dimension)
- **Growth Tracker**: Capability evolution metrics

## Connectome

Key connections (from Nexus "接神经" philosophy):

| From | To | Connection |
|------|----|------------|
| Heartbeat | Event Bus | Scans for dead letters, triggers closure |
| Event Bus | Memory | Closed operations → mid-term memory |
| Event Bus | Quality Gate | All operations → audit log |
| Quality Gate | Growth Tracker | Audit results → capability metrics |
| Memory | Skills | Past patterns → improved workflows |
| Growth Tracker | Heartbeat | Capability regressions → alerts |

## Anti-Patterns (from Nexus lessons)

1. ❌ Using filters instead of fixing root causes
2. ❌ Adjusting thresholds instead of tracing to source
3. ❌ Skipping broken code with `if bad: continue`
4. ❌ Stopping at surface symptoms
5. ❌ Keeping dead code "just in case"
6. ❌ Bare `except:pass` — always log, always classify
