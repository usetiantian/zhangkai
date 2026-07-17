# Event Bus — Five-Step Closed Loop

> From Nexus: CREATE → PUBLISH → CONSUME → FEEDBACK → CLOSURE
> 36 dead letters → 23 dead, 2 orphan → 72% connection rate

## Structure

Every significant operation emits an event to `event-bus/events.jsonl`.
Format: one JSON object per line.

```json
{
  "id": "uuid",
  "ts": "ISO8601",
  "step": "created|published|consumed|feedback|closed",
  "type": "bash|edit|read|skill|decision|error",
  "description": "what happened",
  "parent_id": null,
  "context": {"project": "...", "file": "..."},
  "result": "ok|warning|error|dead_letter"
}
```

## Step Definitions

1. **CREATE** (step: "created")
   - Event is logged at the start of an operation
   - Contains: intent, scope, affected files

2. **PUBLISH** (step: "published")
   - Operation was dispatched to the execution layer
   - Tool call was made, skill was triggered

3. **CONSUME** (step: "consumed")
   - Result was received and processed
   - Downstream effects began

4. **FEEDBACK** (step: "feedback")
   - Outcome classification: ok / warning / error
   - Side effects detected
   - If error: root cause analysis started

5. **CLOSURE** (step: "closed")
   - All resources released
   - All follow-ups completed
   - Memory persisted

## Dead Letter Detection

An event without CLOSURE after session end = dead letter.
Heartbeat scans for:
- Operations that errored but weren't retried
- Follow-ups that were promised but not done
- Resources that were acquired but not released

## Anti-Patterns (from Nexus)

- Don't log and forget — every CREATE must reach CLOSURE
- Don't suppress errors — FEEDBACK must be honest
- Dead letters are NOT "fine" — each one is a broken wire
