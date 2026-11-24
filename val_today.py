
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WD = 'D:/ComfyUI_windows_portable/ComfyUI/user/default/workflows'
info = json.load(open('_oi_check.json', encoding='utf-8'))

def unpack(l):
    if isinstance(l, dict):
        return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type'])
    return tuple(l)

def check_links(nodes, links, err, tag):
    N = {n['id']: n for n in nodes}
    ids = set(N) | {-10, -20}
    for l in links:
        try:
            lid, oid, osl, tid, tsl, ty = unpack(l)
        except Exception:
            err.append((tag + ':unparsable link',)); continue
        if oid not in ids or tid not in ids:
            err.append((tag + ':dangling link' + str(lid),)); continue
        o, t = N.get(oid), N.get(tid)
        if o is None or t is None: continue
        if osl >= len(o.get('outputs', [])) or tsl >= len(t.get('inputs', [])):
            err.append((tag + ':slot overflow link' + str(lid),)); continue
        ot = o['outputs'][osl].get('type'); tt = t['inputs'][tsl].get('type')
        if ot not in ('*', ty) and tt not in ('*', ty):
            err.append((tag + ':type conflict link' + str(lid) + ' ' + str(ot) + '!=' + str(tt),))
        if lid not in (o['outputs'][osl].get('links') or []):
            err.append((tag + ':output backlink missing link' + str(lid),))
        if t['inputs'][tsl].get('link') != lid:
            err.append((tag + ':input backlink missing link' + str(lid),))
    for n in nodes:
        spec = info.get(n.get('type'))
        if not spec: continue
        req = set(spec.get('input', {}).get('required', {}).keys())
        for i in n.get('inputs', []):
            nm = i.get('name')
            if nm in req and not i.get('widget') and i.get('link') is None:
                err.append((tag + ':required input ' + str(nm) + ' of ' + str(n.get('type')) + ' not connected',))

def run(fn):
    F = os.path.join(WD, fn)
    d = json.load(open(F, encoding='utf-8'))
    err = []; types = set()
    for n in d.get('nodes', []): types.add(n.get('type'))
    check_links(d.get('nodes', []), d.get('links', []), err, 'top')
    for si, s in enumerate(d.get('definitions', {}).get('subgraphs', [])):
        for n in s.get('nodes', []): types.add(n.get('type'))
        check_links(s.get('nodes', []), s.get('links', []), err, 'sub' + str(si))
    missing = sorted(t for t in types if t and t not in info)
    print('%-40s types=%3d  missing=%s' % (fn, len(types), missing if missing else 'none'))
    if err:
        print('   link problems: %d' % len(err))
        for e in err[:15]: print('     -', e)
    else:
        print('   links OK')
    return (not missing) and (not err)

files = ['视频换脸_ReActor.json',
         '视频去水印_LaMa高质量.json',
         '歌曲制作台_A_YuE2选曲谱.json',
         '声音克隆.json',
         '视频修补.json']
ok = True
for f in files:
    try: ok = run(f) and ok
    except FileNotFoundError:
        print('%-40s FILE MISSING' % f); ok = False
print('')
print('OVERALL:', 'PASS' if ok else 'FAIL')
