# Implementation Plan: Nexus Autonomous Recovery

**Branch**: `001-nexus-recovery` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-nexus-recovery/spec.md`

## Summary

Restore Nexus autonomous productivity. The system has all the pieces (SelfPlay engine with 338 seeds, 5-type gap system, 5610-node EvoKG, Qwen local inference) but the runtime orchestration is broken: HeartbeatLoop tick crashes, cognitive loop is stuck in reflect, SelfPlay trigger is not wired to timer, and observability is blind. Fix the orchestration layer, reconnect the triggers, make the dashboard honest.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: aiohttp, asyncio, torch 2.11+cu128, ChromaDB, DeepSeek V4 API

**Storage**: JSON files (state, capability_tree, self_play), SQLite (EvoKG), ChromaDB (semantic vectors)

**Testing**: Manual verification via `/api/dashboard`, `/api/monitor`, log inspection

**Target Platform**: Windows 10, RTX 5080, localhost:19666

**Project Type**: Autonomous AI agent runtime

**Performance Goals**: SelfPlay cycle <5min, cognitive loop decision <2s, dashboard response <500ms

**Constraints**: Memory <4GB idle, CPU <50% idle, DeepSeek function calling unreliable (accepted)

**Scale/Scope**: 355 .py files, 8-layer architecture, ~180 active modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Gate | Status |
|---------|------|--------|
| I. Observable First | Dashboard shows real metrics? | FAIL - agent_status has error |
| II. Autonomous by Default | SelfPlay runs on timer? | FAIL - only runs on external trigger |
| III. Memory Discipline | Idle memory <4GB? | FAIL - grows to 5GB+ |
| IV. Simple State | Cognitive loop states clear? | FAIL - forever "reflect" |
| V. Fix Root Cause | Previous fixes at source? | PASS - garbage blocked at entry |
| VI. No Dead Code | Dormant modules documented? | NEEDS AUDIT |
| VII. API Precious | LLM calls tracked? | PASS - GrowthMonitor has counters |

## Project Structure

### Documentation (this feature)

```text
specs/001-nexus-recovery/
├── constitution.md     # Project principles
├── spec.md             # Feature specification (this file's input)
├── plan.md             # This file
├── research.md         # Phase 0: trace exact failure points
├── data-model.md       # Phase 1: state machine definitions
├── quickstart.md       # Phase 1: validation steps
├── contracts/          # Phase 1: API contracts for fixed endpoints
│   └── dashboard-api.md
└── tasks.md            # Phase 2: executable task list
```

### Source Code (existing project)

```text
C:\Users\87999\.nexus\
├── nexus_gateway/
│   └── run.py                    # [MODIFY] Tick error handler
├── nexus_agent/
│   ├── heartbeat_loop.py         # [FIX] get_status(), pulse_driver asyncio bug
│   ├── cognitive_loop/
│   │   └── __init__.py           # [FIX] Decision deadlock
│   ├── self_play_engine.py       # [FIX] Autonomous trigger
│   ├── gap_analyzer/
│   │   └── __init__.py           # [FIX] Gap detection accuracy
│   ├── growth_monitor.py         # [FIX] llm_calls counter
│   ├── autonomous_planner.py     # [FIX] Task completion tracking
│   └── autobiographical_memory.py # [FIX] Memory trimming threshold
```

## Complexity Tracking

> No violations that need justification — this is a recovery, not a new feature.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | - | - |

---

## Phase 0: Research — Trace Exact Failure Points

### 0.1 HeartbeatLoop Tick Crash

**Symptom**: Every 60s tick logs `Tick错误: cannot access local variable 'datetime'`

**Hypothesis**: An `import datetime` or `datetime =` inside a function body in the tick call chain shadows the module-level `from datetime import datetime`. Python 3.12 treats `datetime` as local, then fails when accessed before the assignment.

**Investigation method**:
1. Modified run.py to add `exc_info=True` + `traceback.print_exc()` — already done
2. Check log for full traceback after next restart
3. If traceback doesn't reveal location, instrument heartbeat_loop.tick() with per-step timing

**Fallback if not found**: The `asyncio` bug in `_pulse_driver()` (line 490→541, confirmed by AST) may be the actual crash, with the error message being misleading due to exception chaining. Fix the asyncio bug first and see if datetime error disappears.

### 0.2 Cognitive Loop "Reflect" Deadlock

**Symptom**: Every decision is `{action: 'reflect', confidence: 0.4-0.5, reason: '无紧急缺口, 进入反思模式'}`

**Confirmed from logs**: Sentinel detects stagnation → switches strategy → still nothing to do → Sentinel detects stagnation again. Self-reinforcing loop.

**Root cause hypothesis**: The cognitive loop's priority always returns `score: 3, action: 'analyze'` with `_ema_rate: 0.9806` (stuck EMA). The decision function sees no gaps, Sentinel overrides to reflect, and the cycle repeats. The EMA is never reset by successful actions because there ARE no successful actions.

### 0.3 SelfPlay Autonomous Trigger

**Symptom**: SelfPlay runs when dashboard API is called (via EventBus), but not on its own.

**Confirmed**: At 11:55, our `/api/dashboard` call triggered SelfDirectedLearner which connected to EventBus and restored 4 depleted gaps, causing one SelfPlay cycle to run. Without the API call, nothing triggers it.

**Root cause hypothesis**: SelfPlay engine relies on EventBus events to start cycles. The EventBus is fed by heartbeat_loop's pulse_driver. If pulse_driver is broken (asyncio bug), no events flow, SelfPlay never gets triggered.

### 0.4 GapAnalyzer Zero Gaps

**Symptom**: Reports `发现 0 个未学习知识缺口` while autonomous_planner schedules `capability:code_generation:add/sel` every 2 minutes.

**Root cause hypothesis**: The gap_analyzer scans capability_tree for nodes with `learned < threshold`. The garbage data cleanup may have reset these counts. Also, the autonomous_planner's scheduled tasks may be from a different source (reminder system, not gap detection), creating the appearance of inconsistency.

### 0.5 Memory Growth

**Symptom**: 3.5GB → 5.8GB over 6 hours.

**Root cause hypothesis**: Autobiographical memory keeps 5000 episodes with no size-based trimming. Asyncio tasks accumulate (each `_launch_async` creates a fire-and-forget task). ChromaDB or EvoKG connections may not release resources.

---

## Phase 1: Design

### 1.1 HeartbeatLoop Fix

**Fix `_pulse_driver()` asyncio shadowing** (confirmed by AST):
- File: `nexus_agent/heartbeat_loop.py`
- Line 541: `import asyncio` → remove this import (it's inside an if-block for bilibili, which is already handled elsewhere)
- The function already has `asyncio` from the module-level import

**Add `get_status()` method**:
```python
def get_status(self) -> Dict:
    return {
        "tick_count": self._tick_count,
        "running": self._running,
        "busy": self._busy,
        "pulse_sources": dict(self._pulse_sources),
        "pulse_failures": self._pulse_failures,
    }
```

### 1.2 Cognitive Loop Fix

**Break the reflect deadlock**:
- After 3 consecutive "reflect" decisions with confidence < 0.6, force "explore"
- Reset EMA when a non-reflect action completes successfully
- Sentinel should escalate from MODERATE to HIGH after 5 consecutive same-decisions, forcing a domain exploration

### 1.3 SelfPlay Autonomous Trigger

**Wire SelfPlay to heartbeat timer**:
- Add a `_selfplay_cycle()` to heartbeat_loop's tick, firing every 10 ticks (10 minutes)
- This bypasses the EventBus dependency for the basic trigger
- The EventBus path (for external/dashboard triggers) remains as a bonus

### 1.4 GapAnalyzer Consistency

**Sync with autonomous_planner**:
- Before reporting "0 gaps", query autonomous_planner's pending task queue
- If tasks exist, report them as gaps with source="planner_pending"
- Add a `_cross_validate()` step that compares gap_analyzer output with planner state

### 1.5 Memory Discipline

**Add memory trimming trigger**:
- In GrowthMonitor hourly check: if RSS > 4GB, trigger `autobiographical_memory.trim(aggressive=True)`
- Add `asyncio.Task.all_tasks()` cleanup for completed tasks
- Add periodic `gc.collect()` in the heartbeat idle cycle

### 1.6 Dashboard Honesty

**Fix agent_status**:
- Use the new `HeartbeatLoop.get_status()` method
- Add `llm_calls` tracking: increment counter in the LLM call wrapper
- Add `uptime` from process start time
- Add `cognitive_state` from cognitive loop's current action

---

## Phase 2: Contracts

See `contracts/dashboard-api.md` for the fixed `/api/dashboard` response schema.

---

## Phase 3: Task Breakdown

See `tasks.md` (generated by `/speckit.tasks` equivalent — manual for this recovery).
