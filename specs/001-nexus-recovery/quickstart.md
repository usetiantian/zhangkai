# Quickstart: Nexus Recovery Validation

## Prerequisites

- Nexus gateway running (`nexus_daemon.bat`)
- Port 19666 accessible
- Access to log file: `C:\Users\87999\.nexus\logs\nexus_startup.log`

## Validation Steps

### Step 1: Dashboard Honesty (1 min)

```bash
curl http://127.0.0.1:19666/api/dashboard
```

Expected:
- `agent_status` has NO `error` field
- `system_health.memory_mb` shows actual RSS value
- `system_health.cpu_percent` shows actual CPU usage

### Step 2: Heartbeat Health (5 min)

```bash
# Wait 2 minutes, then check
grep "HeartbeatLoop" logs/nexus_startup.log | tail -5
```

Expected:
- `Tick #N` entries increasing
- No `Tick错误` entries
- No `UnboundLocalError` entries

### Step 3: Autonomous Output (30 min)

```bash
# Wait 30 minutes, then check
curl http://127.0.0.1:19666/api/dashboard
```

Expected:
- `active_learning.cycles_completed > 0`
- `llm_calls > 0` (from `/api/monitor`)

### Step 4: Cognitive Loop Variety (30 min)

```bash
grep "Decision:" logs/nexus_startup.log | tail -10
```

Expected:
- At least 2 different action types in last 10 decisions
- Not all "reflect"

### Step 5: Memory Stability (2 hours)

```bash
# Every 30 minutes
curl http://127.0.0.1:19666/api/dashboard | grep memory_mb
```

Expected:
- All samples under 4000 (4GB)
- No monotonic upward trend

### Step 6: Gap Accuracy (30 min)

```bash
grep "GapAnalyzer" logs/nexus_startup.log | tail -3
```

Expected:
- If autonomous_planner has pending tasks, gap count > 0
- Gap count consistent with planner state
