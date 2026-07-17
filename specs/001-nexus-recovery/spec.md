# Feature Specification: Nexus Autonomous Recovery

**Feature Branch**: `001-nexus-recovery`

**Created**: 2026-07-16

**Status**: Draft

**Vision Context**: Nexus vision is six pillars — Self-Learning, Self-Thinking, Self-Evolving, Self-Modifying, Self-Awareness, Personalizing. We are currently at Pillar 1→2 transition: SelfPlay works (88% success, 338 seeds), training pipeline is connected, but the autonomous runtime orchestration is broken. This recovery fixes the orchestration so pillars 1-2 can actually run, paving the way for pillars 3-6.

**Input**: Nexus gateway runs for 6+ hours with 87.5% CPU, 5GB memory, zero LLM calls, zero tool calls, zero learning. Cognitive loop stuck in permanent "reflect" mode. SelfPlay engine not running autonomously. GapAnalyzer reports 0 gaps despite pending training tasks.

## User Scenarios & Testing

### User Story 1 - Gateway produces measurable autonomous output (Priority: P1)

CC starts the Nexus gateway and leaves it running. After 1 hour, the dashboard shows non-zero values for LLM calls, skills learned, or gaps processed. The system does not require manual chat messages or API calls to generate activity.

**Why this priority**: This is the core definition of "autonomous" — if the system does nothing on its own, it's just a chat bot waiting for input.

**Independent Test**: Start gateway, wait 60 minutes, check `/api/dashboard` → `active_learning.cycles_completed > 0` and `llm_calls > 0`.

**Acceptance Scenarios**:

1. **Given** gateway started fresh, **When** 60 minutes pass, **Then** at least 1 SelfPlay cycle has completed AND at least 1 LLM call has been made.
2. **Given** gateway running idle for 30 minutes, **When** GrowthMonitor hourly report fires, **Then** Knew > 0 or Gaps > 0 (something changed).

---

### User Story 2 - Cognitive loop escapes "reflect" deadlock (Priority: P1)

The cognitive loop currently always decides "reflect" with low confidence because Sentinel detects a loop. After fix, the loop cycles through different modes (analyze → learn → explore → reflect) based on actual system state.

**Why this priority**: The cognitive loop is the brain. If it's stuck, nothing happens.

**Independent Test**: Check logs for 10 consecutive cognitive loop decisions → at least 2 different action types appear (not all "reflect").

**Acceptance Scenarios**:

1. **Given** system has pending training tasks, **When** cognitive loop runs, **Then** decision is "learn" or "explore", not "reflect".
2. **Given** Sentinel detects stagnation, **When** it triggers intervention, **Then** the intervention actually changes behavior (e.g., forces exploration of a new domain).

---

### User Story 3 - Dashboard shows real system status (Priority: P2)

The dashboard `/api/dashboard` currently shows `agent_status: {error: "HeartbeatLoop has no get_status"}` and all-zero learning metrics even when modules are alive. After fix, dashboard reflects actual system health.

**Why this priority**: Without observability, we can't tell if the system is working or broken.

**Independent Test**: Visit `/api/dashboard` → `agent_status` has no error field, `system_health` metrics update in real-time.

**Acceptance Scenarios**:

1. **Given** gateway running, **When** dashboard is queried, **Then** agent_status shows actual heartbeat count, uptime, and current cognitive loop state.
2. **Given** a module fails, **When** dashboard is queried, **Then** the failure is visible in recent_actions or system_health.

---

### User Story 4 - Memory stays under 4GB on idle (Priority: P2)

The gateway currently grows from 3.5GB to 5GB+ over 6 hours. After fix, idle memory stabilizes under 4GB.

**Why this priority**: Unbounded memory growth eventually crashes the process.

**Independent Test**: Start gateway, monitor memory every 10 minutes for 2 hours → stays under 4GB, no continuous upward trend.

**Acceptance Scenarios**:

1. **Given** gateway idle for 2 hours, **When** memory is sampled, **Then** all samples are under 4GB with no monotonic increase.
2. **Given** autobiographical memory has 5000 episodes, **When** system trims, **Then** low-value episodes are removed, count may drop.

---

### User Story 5 - GapAnalyzer detects real gaps (Priority: P3)

Currently reports 0 gaps while autonomous_planner schedules training for `capability:code_generation:add/sel`. After fix, gap analysis is consistent with training state.

**Why this priority**: The learning pipeline depends on accurate gap detection.

**Independent Test**: After gateway runs for 30 minutes, gap count matches actual pending training items.

**Acceptance Scenarios**:

1. **Given** autonomous_planner has pending training tasks, **When** gap_analyzer runs, **Then** it reports >0 gaps corresponding to those tasks.
2. **Given** a capability has been successfully learned, **When** gap_analyzer runs, **Then** that capability no longer appears as a gap.

---

### Edge Cases

- What happens when DeepSeek API is rate-limited? → System should gracefully back off, not crash the tick loop.
- What happens when SelfPlay has 0 seeds? → Should log a clear warning, not silently do nothing.
- What happens when ChromaDB is unavailable? → Should fall back to file-based storage, not crash.

## Requirements

### Functional Requirements

- **FR-001**: SelfPlay engine MUST run on a 5-minute timer independent of external API calls
- **FR-002**: Cognitive loop MUST transition out of "reflect" within 3 consecutive cycles if system state warrants action
- **FR-003**: Dashboard agent_status MUST include heartbeat_count, uptime, current_cognitive_state
- **FR-004**: GrowthMonitor MUST report actual LLM call count, not null
- **FR-005**: HeartbeatLoop MUST implement get_status() method
- **FR-006**: Memory trimming MUST activate when RSS exceeds 4GB
- **FR-007**: GapAnalyzer MUST read autonomous_planner's pending task queue before reporting 0 gaps
- **FR-008**: Every asyncio.create_task MUST have a name parameter for debugging

### Key Entities

- **CognitiveLoop**: Decision engine with states {analyze, learn, explore, reflect, idle}
- **HeartbeatLoop**: Pulse driver at 60s intervals, triggers SelfPlay, knowledge extraction, health checks
- **SelfPlayEngine**: Autonomous code generation and verification across 13 domains
- **GapAnalyzer**: Scans capability tree for unlearned skills and routes to training
- **GrowthMonitor**: Hourly health report (API calls, memory, gaps, skills)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Gateway achieves >0 LLM calls and >0 learning cycles within 60 minutes of idle runtime
- **SC-002**: Dashboard agent_status returns valid data (no error field) within 1 minute of startup
- **SC-003**: Memory usage stabilizes under 4GB within 2 hours of idle runtime
- **SC-004**: Cognitive loop produces at least 2 different action types in any 10-cycle window
- **SC-005**: GapAnalyzer reports >0 gaps when training tasks exist

## Assumptions

- DeepSeek V4 API is available and functional (function calling limitations accepted)
- The 8-layer architecture design is correct; implementation bugs are the problem, not the design
- 365 Python files exist; ~50 may be dead code; the rest are needed
- Qwen 2B local model is available for SelfPlay Tier1
- No new features are being added — this is pure recovery and stabilization
