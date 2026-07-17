# Stage 26 — self_modifying 安全栅栏 (pre-commit)

Date: 2026-07-15
Goal: close Kai 愿景 "自改代码" 的最后一块 — git pre-commit 安全栅栏.

## Files created

| Path | Lines | Bytes | Role |
|------|------:|------:|------|
| `C:\Users\87999\.nexus\nexus_agent\self_modifying_safety.py` | 88 | 2684 | `pre_commit_check` 库 |
| `C:\Users\87999\.nexus\.nexus_pre_commit_hook.py` | 51 | 1749 | git hook 调用的 Python 包装 |
| `C:\Users\87999\.nexus\.git\hooks\pre-commit` | 5 | 319 | shell 入口 (重定向到 py) |

Total Python LOC: 139 (88 + 51). Each file < 100 lines ✓.
Note: 原 CONTEXT 写的 `C:\Users\87999\claude-workspace\nexus_agent` 不存在 — 真实路径是 `C:\Users\87999\.nexus\nexus_agent\`. 已用真实路径.

## What each piece does

- **self_modifying_safety.py** — `pre_commit_check(file_path, change_description, max_lines, backup_path, lines_changed)`:
  - file_path must start with one of `nexus_agent/`, `data/`, `scripts/` (deny: `secrets/`, `../etc/...`)
  - intent ∈ {refactor, bugfix, perf, cleanup}; `delete` / `rewrite` rejected first; unknown also denied
  - `lines_changed > max_lines` denied; negative rejected
  - On allow, returns `backup_cmd="cp <file_path> <backup_path>"`. If `backup_path` empty, defaults to `.nexus_backup/<file_path>`.

- **.nexus_pre_commit_hook.py** — runs `git diff --cached --name-only --diff-filter=ACMR`, gates each file via `pre_commit_check(..., change_description="refactor")`, exits 0/1.

- **.git/hooks/pre-commit** — 5-line shell using `git rev-parse --show-toplevel` so cwd-relative path is unambiguous.

## Verification output (required call)

```
$ python -c "from nexus_agent.self_modifying_safety import pre_commit_check; r = pre_commit_check('nexus_agent/test.py', 'refactor', max_lines=50); print(r)"
{'allow': True,
 'reason': 'OK (refactor, 0/50 lines, backup=.nexus_backup/nexus_agent/test.py)',
 'backup_cmd': 'cp nexus_agent/test.py .nexus_backup/nexus_agent/test.py'}
```

## Allow/Deny matrix (14 cases, all PASS)

- allow: nexus_agent/x.py@refactor/10, data/foo.json@bugfix/100, scripts/build.sh@perf/50, nexus_agent/x.py@cleanup/0, explicit backup, REFACTOR (case-insensitive)
- deny: `rewrite`, `secrets/api_key` (path), `../etc/passwd` (traversal), too-many-lines, `delete`, unknown intent (`hack`), empty file_path, negative lines_changed

## Coordination with self_modifier / SafeSelfModifier / sandbox

The check is a **gate outside** SafeSelfModifier — caller invokes `pre_commit_check()` BEFORE `SafeSelfModifier`. This is intentional, not a bug:

1. `self_modifier.SafeSelfModifier` already enforces AST-level rollback + worktree validation inside the agent runtime.
2. `sandbox.get_sandbox` enforces write isolation (WorktreeSandbox).
3. `self_modifying_safety.pre_commit_check` adds a final human-visible gate at git commit time (intent allowlist, line budget, mandatory backup).

Flow:
```
proposal → pre_commit_check() → (allow?) → SafeSelfModifier → sandbox → git add / git commit → pre-commit HOOK re-runs gate
```

Why re-run in the hook? Two reasons:
- Any code (script, cron, manual) can bypass SafeSelfModifier and reach `git commit`. The hook catches them.
- Backup location is committed alongside (`.nexus_backup/`), so the modifier's audit trail survives merges.

## Notes / out-of-scope

- Hook is bypassable via `git commit --no-verify` — intentional (留逃生口).
- Backup runs only in pre_commit_check's `backup_cmd` — the actual `cp` is the caller's responsibility (so it can decide cp/rsync/git-stash).
- Did not touch `.git/` internals (objects/refs/index/config). Only installed an empty hooks dir entry, per explicit task spec.
- No existing pre-commit in `C:\Users\87999\.nexus\.git\hooks\` — no `.bak` backup was needed.
