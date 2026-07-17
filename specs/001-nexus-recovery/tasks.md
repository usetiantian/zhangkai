# Tasks: Nexus Autonomous Recovery

**Input**: Design documents from `specs/001-nexus-recovery/`

**Prerequisites**: plan.md (required), spec.md (required), constitution.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)

---

## Phase 1: Setup (Observability Foundation)

**Purpose**: Make the system observable before changing behavior

- [ ] T001 [P] [US3] Add `HeartbeatLoop.get_status()` method in `heartbeat_loop.py`
- [ ] T002 [P] [US3] Fix dashboard `agent_status` to call `get_status()` instead of failing
- [ ] T003 [P] [US3] Add LLM call counter in GrowthMonitor — increment on every API call
- [ ] T004 [US3] Fix dashboard `/api/dashboard` to return real `active_learning` metrics

**Checkpoint**: Dashboard shows real data — heartbeat count, uptime, cognitive state

---

## Phase 2: Foundational (Fix the Heartbeat)

**Purpose**: The heartbeat drives everything. It must work first.

- [ ] T005 [US1] Fix `_pulse_driver()` asyncio shadowing bug in `heartbeat_loop.py` (remove `import asyncio` at line 541)
- [ ] T006 [US1] Add `traceback.print_exc()` to all silent `except Exception: pass` blocks in heartbeat_loop
- [ ] T007 [US1] Verify heartbeat tick runs without errors for 5 consecutive ticks

**Checkpoint**: Heartbeat ticks cleanly. Log shows no Tick errors. Pulse driver running.

---

## Phase 3: User Story 1 — Autonomous Output (Priority: P1)

**Goal**: Gateway produces measurable activity without external input

**Independent Test**: Start gateway, wait 30 min, check `/api/dashboard` → `cycles_completed > 0`

### Implementation for User Story 1

- [ ] T008 [P] [US1] Add `_selfplay_cycle()` to heartbeat_loop tick, fire every 10 ticks
- [ ] T009 [P] [US1] Wire GrowthMonitor `llm_calls` counter to actual API call path
- [ ] T010 [US1] Fix `autonomous_planner` task completion — mark tasks as done when executed
- [ ] T011 [US1] Restart gateway with `sp: 338` seeds active (they need restart to take effect)

**Checkpoint**: After 30 minutes, dashboard shows >0 LLM calls and >0 learning cycles

---

## Phase 4: User Story 2 — Cognitive Loop Escape (Priority: P1)

**Goal**: Cognitive loop cycles through different modes based on actual system state

**Independent Test**: Check 10 consecutive decision logs → at least 2 different action types

### Implementation for User Story 2

- [ ] T012 [US2] Add "reflect counter" — after 3 consecutive reflects with confidence < 0.6, force "explore"
- [ ] T013 [US2] Reset EMA on successful non-reflect action completion
- [ ] T014 [US2] Sentinel escalation: MODERATE → HIGH after 5 same-decisions, force domain exploration
- [ ] T015 [US2] Add `_force_explore()` that picks a random domain from EvoKG and creates a curiosity ticket

**Checkpoint**: Decision log shows variety: analyze, explore, learn — not just reflect

---

## Phase 5: User Story 3 — Dashboard Honesty (Priority: P2)

**Goal**: Dashboard reflects real system state without errors

**Independent Test**: Visit `/api/dashboard` → no error field, metrics update in real-time

### Implementation for User Story 3

- [ ] T016 [US3] Wire `cognitive_state` field to dashboard — show current cognitive loop action
- [ ] T017 [US3] Add `recent_actions` population — log last 10 significant events
- [ ] T018 [US3] Fix `MemoryMB` to show actual RSS, not hardcoded value

**Checkpoint**: Dashboard shows: heartbeat=N, state=exploring, memory=3.2GB, no errors

---

## Phase 6: User Story 4 — Memory Discipline (Priority: P2)

**Goal**: Memory stabilizes under 4GB during idle

**Independent Test**: Monitor memory for 2 hours → all samples under 4GB

### Implementation for User Story 4

- [ ] T019 [US4] Add aggressive trim trigger in GrowthMonitor: if RSS > 4GB, trim autobiographical memory
- [ ] T020 [US4] Add completed asyncio task cleanup in heartbeat idle cycle
- [ ] T021 [US4] Add `gc.collect()` call every 30 ticks in heartbeat

**Checkpoint**: Memory growth curve flattens. Peak stays under 4GB.

---

## Phase 7: User Story 5 — Gap Detection Accuracy (Priority: P3)

**Goal**: GapAnalyzer reports gaps consistent with actual system state

**Independent Test**: After 30min runtime, gap count matches pending training items

### Implementation for User Story 5

- [ ] T022 [US5] Add `_cross_validate()` to gap_analyzer — compare output with autonomous_planner pending queue
- [ ] T023 [US5] If planner has pending tasks but gap_analyzer reports 0, surface those tasks as gaps
- [ ] T024 [US5] Add source tag to gaps: "capability_tree", "planner_pending", "performance"

**Checkpoint**: gap_analyzer report shows N gaps when N training tasks are pending

---

## Phase 8: Polish & Validation

**Purpose**: End-to-end verification

- [ ] T025 Run `quickstart.md` validation steps
- [ ] T026 Verify all 5 user stories independently
- [ ] T027 Run gateway for 2 hours, collect GrowthMonitor reports, verify upward trend in Knew/Learn

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: No dependencies — parallel with Phase 1
- **US1 (Phase 3)**: Depends on Phase 2 (heartbeat must work)
- **US2 (Phase 4)**: Depends on Phase 3 (needs something to actually happen)
- **US3 (Phase 5)**: Depends on Phase 1 (observability foundation)
- **US4 (Phase 6)**: No hard dependency — can run anytime
- **US5 (Phase 7)**: Depends on Phase 3 (needs the system to be running)
- **Polish (Phase 8)**: Depends on all previous phases

### Parallel Opportunities

- Phase 1 + Phase 2 can run in parallel
- T001, T002, T003 within Phase 1 are all independent [P]
- T008, T009 within Phase 3 are independent [P]
- T019, T020, T021 within Phase 6 are independent [P]

---

## Implementation Strategy: Fix Fastest First

1. **Day 1 (today)**: Phase 1 + Phase 2 — make heartbeat work, make dashboard honest
2. **Day 1 (today)**: Phase 4 — break the cognitive loop deadlock
3. **Day 1 (today)**: Phase 3 — wire SelfPlay to timer
4. **Day 2**: Phase 5 + Phase 6 — polish
5. **Day 2**: Phase 7 — gap accuracy
6. **Day 2**: Phase 8 — validate

Total: ~27 tasks, estimated 2 days.

---

## Notes

- All changes are in existing files — no new modules
- DeepSeek V4 function calling limitation is ACCEPTED — we work around it
- sp: 338 seeds already exist, just need timer trigger
- EvoKG 5610 nodes already exist, just need cognitive loop to explore them
