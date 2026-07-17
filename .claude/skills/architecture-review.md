# Skill: Architecture Review + ADR

## Trigger
User asks "architecture", "ADR", "design review", "架构".

## Workflow

### Step 1: Get Architecture Overview
- `get_architecture(aspects=["all"])` → clusters, packages, dependencies

### Step 2: Identify Key Modules
- Sort clusters by member count
- Flag cohesion < 0.5 (split candidates)
- Flag cross-cluster edges > 50% (merge candidates)

### Step 3: Trace Critical Paths
- Main entry → core logic → output
- `trace_path` for key data flows
- Find bottlenecks (loop_depth >= 3, linear_scan_in_loop)

### Step 4: Dependency Analysis
- External dependencies (Cargo.toml / package.json)
- Internal coupling (inter-cluster edges)
- Circular dependency check

### Step 5: Write ADR
- Title: decision
- Context: current state, problem
- Decision: what we chose
- Consequences: trade-offs

## Output
```
# ADR: [Title]

## Context
[Current architecture, problem statement]

## Decision
[What we decided and why]

## Consequences
- Positive: [benefits]
- Negative: [trade-offs / costs]
- Mitigations: [how we handle negatives]
```

## Tools
- codebase-memory: `get_architecture`, `trace_path`, `query_graph`, `manage_adr`
- Bash: `rg` for dependency scanning
