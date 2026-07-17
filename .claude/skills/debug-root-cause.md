# Skill: Root Cause Debugging (Three-Layer Rule)

## Trigger
Bug report, error message, unexpected behavior.
**CRITICAL**: Before ANY fix, chase three layers.

## Workflow

### Layer 1: SURFACE — What happened?
- Exact error message / behavior
- Reproduction steps
- When did it start? (git bisect if possible)

### Layer 2: DIRECT CAUSE — Why did it happen?
- Read the failing code
- Trace data flow to the failure point
- Identify the proximate cause (wrong value, missing function, type error)

### Layer 3: ROOT CAUSE — Why was it allowed to happen?
- Why wasn't this caught earlier? (missing test? missing validation?)
- Is there a systemic pattern? (same bug class elsewhere?)
- What design assumption was violated?

## Anti-patterns (DO NOT DO)
- ❌ Skip to the fix at Layer 1 → will reoccur
- ❌ Filter/suppress the symptom → hides root cause
- ❌ Adjust threshold/magic number → masks the real problem
- ❌ Add `if bad: continue` → ask WHY bad happens

## Tools
- Bash: `rg` for pattern search across codebase
- codebase-memory: `trace_path` for data flow, `search_graph` for callers
- Read: source files at the failure path
- git: `git log`, `git diff`

## Output
```
Root Cause Chain:
  [Layer 1] symptom
    → [Layer 2] direct cause
      → [Layer 3] root cause (design flaw / missing guard / systemic pattern)

Fix:
  [Addresses Layer 3]

Prevention:
  [What test/guard/pattern would have caught this]
```
