# Dashboard API Contract (Fixed)

## GET /api/dashboard

### Response Schema

```json
{
  "recent_actions": [
    {
      "timestamp": "2026-07-16T12:00:00",
      "type": "selfplay.complete",
      "detail": "pattern_completion: 1 solved, score=0.88"
    }
  ],
  "eval_trend": [
    {"timestamp": "...", "composite": 0.68}
  ],
  "system_health": {
    "agent_available": true,
    "llm_available": true,
    "memory_mb": 3200,
    "cpu_percent": 35.0
  },
  "active_learning": {
    "cycles_completed": 12,
    "gaps_detected": 3,
    "plans_created": 2,
    "practice_sessions": 5,
    "improvements": 1
  },
  "agent_status": {
    "heartbeat_count": 45,
    "uptime_seconds": 2700,
    "cognitive_state": "exploring",
    "running": true
  },
  "test_stats": {
    "total": 32,
    "passed": 32,
    "failed": 0
  }
}
```

### Field Contract

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_status` | object | Yes | Must NOT contain `error` field |
| `agent_status.heartbeat_count` | int | Yes | Current tick count |
| `agent_status.uptime_seconds` | float | Yes | Seconds since startup |
| `agent_status.cognitive_state` | string | Yes | Current action: analyze/learn/explore/reflect/idle |
| `system_health.memory_mb` | float | Yes | Actual RSS, not hardcoded |
| `system_health.cpu_percent` | float | Yes | Actual CPU usage |
| `active_learning.cycles_completed` | int | Yes | >0 when SelfPlay has run |
| `recent_actions` | array | Yes | Last 10 significant events |

## GET /api/monitor

### Response Schema

```json
{
  "uptime": 2700.0,
  "llm_calls": 15,
  "tool_calls": 3,
  "memory_mb": 3200.0
}
```

### Field Contract

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `llm_calls` | int | Yes | Must NOT be null. Incremented on every API call. |
| `tool_calls` | int | Yes | Incremented on every tool execution. |

## GET /api/health

### Response Schema (unchanged)

```json
{
  "status": "ok",
  "timestamp": 1784174061.35
}
```
