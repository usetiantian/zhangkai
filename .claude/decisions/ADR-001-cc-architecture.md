# ADR-001: CC Architecture v2.0 — Nexus-Inspired Self-Architecture

## Date
2026-07-17

## Status
Accepted

## Context
CC had scattered capabilities (tools, MCPs, skills) but no unifying architecture.
Grok Build analysis revealed 8 capabilities that could be ported.
Nexus diary provided a proven design philosophy: closed-loop event bus, layered memory, constitutional boundaries, self-audit, growth tracking.

User requested: "按Nexus的思想完成你自己的架构"

## Decision
Adopt a 4-layer architecture:

- **Layer 0**: Constitution (6 immutable principles, CC cannot modify)
- **Layer 1**: Core Subsystems (Event Bus, Heartbeat, Memory Stack)
- **Layer 2**: Execution (Tools + Skills)
- **Layer 3**: Reflection (Quality Gate + Growth Tracker)

All layers connected by an event bus following Nexus's five-step closed loop:
CREATE → PUBLISH → CONSUME → FEEDBACK → CLOSURE

## Consequences

### Positive
- Every operation is traceable (event bus)
- Knowledge persists across sessions (three-layer memory)
- Capability growth is measurable (growth tracker)
- Errors don't repeat (bug patterns → memory → skills)
- Architecture decisions are recorded (ADR log)
- CC can self-audit (quality gate)
- CC can self-improve within constitutional bounds

### Negative
- Additional overhead per operation (event logging)
- Memory entities need periodic review (stale knowledge risk)
- Constitution constrains CC's autonomy (by design)

### Mitigations
- Event logging is lightweight (append-only JSONL)
- Memory review is part of Heartbeat
- Constitution amendment has a clear procedure

## Related
- Nexus Diary, 2026-07-09: "不是修bug，是种种子"
- `constitution.md`: A0-A5 principles
- `architecture.md`: Full system design
