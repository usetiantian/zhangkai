import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

S = os.path.expanduser('~/.claude/settings.json')
d = json.load(open(S, encoding='utf-8'))
changes = []

env = d.setdefault('env', {})
if env.pop('CLAUDE_CODE_SIMPLE', None) is not None:
    changes.append('env.CLAUDE_CODE_SIMPLE: 1 -> REMOVED (restore CLAUDE.md discovery, plugin sync, LSP, auto-memory)')

allow = d['permissions'].setdefault('allow', [])
for old, new in (('Read(*)', 'Read'), ('Write(*)', 'Write'), ('Edit(*)', 'Edit')):
    if old in allow:
        allow[allow.index(old)] = new
        changes.append('permissions.allow: "%s" -> "%s" (2.1.x: (*) only covers working dir, bare name = all paths)' % (old, new))

new_deny = [
    "Bash(rm -rf /)", "Bash(rm -rf ~)", "Bash(rm -rf $HOME)", "Bash(rm -rf $HOME/*)",
    "Bash(format *)", "Bash(diskpart *)", "Bash(shutdown *)",
    "Bash(rmdir /s C:*)", "Bash(rmdir /s D:*)",
    "Bash(del /f /s C:*)", "Bash(del /f /s D:*)",
]
if d['permissions'].get('deny', []) != new_deny:
    d['permissions']['deny'] = new_deny
    changes.append('permissions.deny: narrowed to 11 literal rules (old "rm -rf *" hard-blocked scoped deletes like rm -rf /tmp/x)')

d['permissions']['defaultMode'] = 'auto'
changes.append('permissions.defaultMode: -> "auto" (the autoMode.environment block was never actually activated)')

TOOLS = os.path.expanduser('~/.claude/tools')
TOOLS_POSIX = TOOLS.replace(os.sep, '/')
for k, v in {
    'ATOMGIT_API': 'https://api.atomgit.com/api/v5',
    'ATOMGIT_HUB': 'https://hub.atomgit.com',
    'ATOMGIT_WEB': 'https://atomgit.com',
    'ATOMGIT_TOOLS': TOOLS_POSIX,
}.items():
    if env.get(k) != v:
        env[k] = v
        changes.append('env.%s: -> %s' % (k, v))

pyp = env.get('PYTHONPATH', '')
if TOOLS_POSIX not in pyp.split(os.pathsep):
    env['PYTHONPATH'] = (pyp + os.pathsep + TOOLS_POSIX).strip(os.pathsep)
    changes.append('env.PYTHONPATH: appended ~/.claude/tools')

EVENTS = {'PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'SessionStart', 'SessionEnd',
          'Stop', 'SubagentStop', 'PreCompact', 'PostCompact', 'Notification',
          'UserPromptSubmit', 'TaskCompleted'}
uh = os.path.expanduser('~/.claude/hooks/hooks.json')
if os.path.exists(uh):
    ud = json.load(open(uh, encoding='utf-8'))
    user_hooks = {k: v for k, v in ud.items() if k in EVENTS}
    d.setdefault('hooks', {})
    for ev, arr in user_hooks.items():
        d['hooks'][ev] = arr
    changes.append('hooks: wired %d user-level events (%s) - previously ~/.claude/hooks/hooks.json was a reference doc, never loaded'
                   % (len(user_hooks), ', '.join(sorted(user_hooks))))

with open(S, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print('written:', S)
for c in changes:
    print('  *', c)
