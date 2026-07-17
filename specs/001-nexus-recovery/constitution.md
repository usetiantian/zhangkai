# Nexus Constitution

## Preamble

Nexus is an autonomous AI system with six pillars:

> **自主学习** (Self-Learning) → **自主思考** (Self-Thinking) → **自主进化** (Self-Evolving) → **自改代码** (Self-Modifying) → **自我意识** (Self-Awareness) → **越用越懂我** (Personalizing)

It is not a chatbot. It is not a tool. It is a continuously running autonomous agent that learns from its own SelfPlay, evolves its own code, builds a model of itself, and grows more useful to its user over time.

## Core Principles

### I. Autonomous First

Nexus MUST generate productive activity without external input. It does not wait for messages, webhooks, or API calls. It runs its own SelfPlay cycles, explores its own knowledge gaps, and evolves its own capabilities on a timer.

- SelfPlay engine runs on heartbeat timer, not external trigger
- Cognitive loop cycles through analyze/learn/explore/reflect based on system state
- Zero external input → non-zero output within 60 minutes

### II. Six Pillars in Order

Each pillar builds on the previous. Do not skip ahead.

1. **Self-Learning**: SelfPlay produces training data → Qwen LoRA improves
2. **Self-Thinking**: Cognitive loop makes autonomous decisions about what to learn
3. **Self-Evolving**: EvolutionEngine generates and verifies code fixes
4. **Self-Modifying**: Sandbox-verified code changes go live via hot reload
5. **Self-Awareness**: CapabilityTree + MetaCognition produce a real self-model
6. **Personalizing**: UserModel accumulates preferences, ContextOrchestrator injects them

### III. Observable Always

Every subsystem exposes health status. No silent failures.

- Dashboard `/api/dashboard` shows real-time truth
- GrowthMonitor reports non-zero metrics when work happens
- Every async task logs start, result, duration
- `ERROR = 0` is the standard for a running system

### IV. Six-Stage Workflow (CC Discipline)

Every change follows the six stages. No skipping.

1. **Architecture** → Draw the full picture. Answer: upstream/downstream? Impact scope? How to verify?
2. **Execution** → Modify code. Check all callers. Verify compilation.
3. **Verification** → 31 checks: compile, import, unit test, integration, vulture
4. **Run** → Restart Nexus. Watch logs 5 minutes. `grep ERROR` must be zero.
5. **Debug** (if needed) → Stop. Redraw. Understand before continuing.
6. **Delivery** → Git commit + diary (narrative style, with numbers and lessons) + cleanup

### V. Root Cause Over Filter

When a problem is found, trace to the source. Do not add filters downstream.

- "源头治理 > 过滤拦截 > 跳过不管"
- If garbage enters the pipeline, fix the entry point
- If a module crashes, fix the module, not the caller's error handler
- Chase three layers deep: symptom → direct cause → root cause

### VI. Memory Discipline

Memory usage must be bounded.

- Idle memory under 4GB
- Autobiographical memory quality over quantity (not just "keep 5000")
- Completed asyncio tasks must be cleaned up

### VII. API Calls Are Precious

Every LLM call costs. Zero waste.

- No call without clear purpose and expected output
- Batch where possible. Cache with TTL.
- Track cost per call and per session

### VIII. No Dead Code

Dead code is deleted, not kept "just in case."

- Every module has a known layer (from the 8-layer architecture)
- Dormant modules go in a documented registry
- Git history preserves the past; the codebase stays clean

### IX. Diary Discipline

Every work session ends with a diary entry.

- Narrative style: what was discovered → how it was analyzed → what was fixed → what was learned
- Must have numbers: files changed, lines modified, tests passed
- Must have lessons: what mistakes were made, what to do differently tomorrow

## Governance

This constitution supersedes all other development practices.
All changes must be verified against these principles.
The six-stage workflow is non-negotiable.
The diary is non-negotiable.

**Version**: 1.0.0 | **Ratified**: 2026-07-16 | **Last Amended**: 2026-07-16
