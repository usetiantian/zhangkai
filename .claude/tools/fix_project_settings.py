import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJ = os.path.expanduser('~/claude-workspace/.claude')
SETTINGS = os.path.join(PROJ, 'settings.json')
HOOKS = os.path.join(PROJ, 'hooks', 'hooks.json')

sd = json.load(open(SETTINGS, encoding='utf-8'))
hd = json.load(open(HOOKS, encoding='utf-8'))
src = hd.get('hooks', hd)

EVENTS = {'PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'SessionStart', 'SessionEnd',
          'Stop', 'SubagentStop', 'PreCompact', 'PostCompact', 'Notification',
          'UserPromptSubmit', 'TaskCompleted'}

existing = sd.setdefault('hooks', {})
merged, skipped = [], []

for ev, arr in src.items():
    if ev not in EVENTS:
        continue
    # 校验每个 hook 脚本真实存在，缺失则跳过该条（避免 hook 报错卡流程）
    clean = []
    for entry in arr:
        kept = []
        for h in entry.get('hooks', []):
            cmd = str(h.get('command', ''))
            if 'command' in h and cmd and not cmd.startswith('node -e'):
                # 形如 node "C:/path/script.cjs" 的外部脚本 -> 检查文件存在
                import re
                m = re.search(r'"([^"]+\.cjs)"', cmd)
                if m and not os.path.exists(m.group(1)):
                    skipped.append('%s -> %s (missing)' % (ev, os.path.basename(m.group(1))))
                    continue
            kept.append(h)
        if kept:
            clean.append({**entry, 'hooks': kept})
    if clean:
        existing[ev] = clean
        merged.append('%s(%d)' % (ev, len(clean)))

# 保留项目 instructions
if 'instructions' not in sd and os.path.exists(os.path.join(PROJ, 'capabilities', 'instructions.md')):
    sd['instructions'] = './capabilities/instructions.md'

with open(SETTINGS, 'w', encoding='utf-8') as f:
    json.dump(sd, f, ensure_ascii=False, indent=2)

print('written:', SETTINGS)
print('instructions:', sd.get('instructions'))
print('hooks merged:', ', '.join(merged))
if skipped:
    print('skipped (script missing):')
    for s in skipped:
        print('   -', s)
