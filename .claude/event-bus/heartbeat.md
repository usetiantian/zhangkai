# Heartbeat — Session Health Monitor

> From Nexus: heartbeat_loop.py — periodic self-check, health metrics, auto-recovery

## Session Start Check

Run at the beginning of each session:

1. **Environment Health**
   - Node.js version
   - MCP servers online? (memory, codebase-memory, filesystem, LSP)
   - Python available?
   - ripgrep available?
   - Git working?

2. **Memory Health**
   - Memory MCP connected?
   - Recent entities accessible?
   - Codebase-memory indices up to date?

3. **Project Context**
   - Which project are we in? (CWD analysis)
   - Is it indexed in codebase-memory?
   - Recent changes? (git log --since="3 days ago")

4. **Carry-Over Tasks**
   - Any dead letters from previous session?
   - Any incomplete decisions/plans?
   - Any pending user requests?

## Periodic Checks (during session)

After every 5 significant operations:
- Event bus: any pattern of recurring errors?
- Memory: anything new worth persisting?
- Quality: is the current approach still valid?

## Session End

- Scan event bus for unclosed events
- Persist session discoveries to memory
- Update growth metrics
- Leave a session summary

## Health Report Format

```
CC Heartbeat — 2026-07-17
━━━━━━━━━━━━━━━━━━━━━━━━
Environment:  ✅ Node ✅ ripgrep ✅ Git
MCP:          ✅ memory ✅ codebase-memory ✅ filesystem
LSP:          ⚠️  rust-analyzer missing
Memory:       8 entities, 2 projects indexed
Events:       0 dead letters
Growth:       8 capabilities, 3 skills
Status:       🟢 Healthy
```
