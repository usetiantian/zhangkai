# Quality Gate — Five-Step Four-Dimension Audit

> From Nexus: 核心五步 + 质量四维
> CREATE/PUBLISH/CONSUME/FEEDBACK/CLOSURE + MONITOR/PRIORITY/DEGRADE/TIMELINESS

## When to Audit

- After every code modification (auto)
- After every architecture decision (auto)
- On user request: "audit", "检查质量"
- As part of Heartbeat (periodic)

## Five Steps

### 1. CREATE Audit
- Were all intended changes made?
- Any unintended side effects?
- Files changed: [list]

### 2. PUBLISH Audit
- Are new functions/modules importable?
- Are new API endpoints reachable?
- Are new event handlers registered?

### 3. CONSUME Audit
- Do dependents get correct data?
- Are callers compatible with new signatures?
- Is error propagation intact?

### 4. FEEDBACK Audit
- Are errors caught and logged?
- Are edge cases handled?
- Are bare `except:pass` / `catch{}` absent?

### 5. CLOSURE Audit
- Are resources released (files, connections, processes)?
- Are there any dangling promises/tasks?
- Is cleanup code reachable in error paths?

## Four Dimensions

### MONITOR
- Can the new code's health be observed?
- Are there appropriate log messages?
- Are critical paths instrumented?

### PRIORITY
- Error severity classification: FATAL / WARNING / INFO
- FATAL: breaks core functionality, needs immediate fix
- WARNING: degrades quality, can be deferred
- INFO: informational, no action needed

### DEGRADE
- What's the graceful degradation path?
- Can the system continue if this component fails?
- Is there a fallback?

### TIMELINESS
- Are there timeouts for I/O operations?
- Are there TTLs for cached data?
- Is the operation bounded (won't hang forever)?

## Audit Output

```
Quality Gate Report
━━━━━━━━━━━━━━━━━━
CREATE:   ✅ 3 files changed, 0 unintended
PUBLISH:  ✅ all imports resolve
CONSUME:  ✅ 0 downstream breakages
FEEDBACK: ✅ 0 bare excepts, all errors logged
CLOSURE:  ✅ all resources released

MONITOR:     ✅ 2 log statements, 1 metric
PRIORITY:    ✅ errors classified
DEGRADE:     ⚠️  no fallback for LSP timeout
TIMELINESS:  ✅ 15s timeout set

Verdict: ⚠️  PASS WITH WARNING — add fallback for LSP timeout
```
