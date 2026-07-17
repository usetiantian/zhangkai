# Skill: Code Audit (Five-Step Four-Dimension)

## Trigger
User asks "audit", "review quality", "检查质量", "审计", or after major changes.

## Workflow

### Step 1: CREATE — enumerate all code paths introduced
- git diff to see what changed
- list new functions, classes, modules

### Step 2: PUBLISH — verify each is reachable
- trace_path for each new function → verify callers exist
- check imports resolve

### Step 3: CONSUME — verify integration
- trace_path inbound → are dependents getting correct data?
- check event bus / callback registrations

### Step 4: FEEDBACK — error handling completeness
- grep for `except:`, `except Exception:`, `catch {}`, `.catch(`
- classify each: has log? has recovery? has re-raise?
- flag bare excepts

### Step 5: CLOSURE — resource lifecycle
- check open/close, start/stop, acquire/release pairs
- verify cleanup in error paths too

## Quality Four Dimensions
- **MONITOR**: health checks, metrics, logging
- **PRIORITY**: error severity classification
- **DEGRADE**: graceful degradation paths
- **TIMELINESS**: timeouts, TTLs, deadlines

## Output
| Step | Status | Issues |
|------|:------:|--------|
| CREATE | ✅/⚠️/🔴 | count |
| PUBLISH | ✅/⚠️/🔴 | count |
| CONSUME | ✅/⚠️/🔴 | count |
| FEEDBACK | ✅/⚠️/🔴 | count |
| CLOSURE | ✅/⚠️/🔴 | count |

## Tools
- Bash: `git diff`, `rg`
- codebase-memory: `search_graph`, `trace_path`, `query_graph`
