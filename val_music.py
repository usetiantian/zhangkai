import json, os, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
info = json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=40))
WD = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
def unpack(l):
    return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']) if isinstance(l, dict) else tuple(l)
F = os.path.join(WD, '歌曲制作台_A_YuE2选曲谱.json')
d = json.load(open(F, encoding='utf-8'))
types = set()
for n in d['nodes']: types.add(n.get('type'))
for s in d.get('definitions', {}).get('subgraphs', []):
    for n in s['nodes']: types.add(n.get('type'))
miss = [t for t in sorted(types) if t and t not in info and len(t) != 36]
print('节点类型 %d | 缺失: %s' % (len(types), miss if miss else '无'))
err = []
for s in d.get('definitions', {}).get('subgraphs', []):
    N = {n['id']: n for n in s['nodes']}; ids = set(N) | {-10, -20}
    for l in s['links']:
        lid, oid, osl, tid, tsl, ty = unpack(l)
        if oid not in ids or tid not in ids: err.append(('缺失', lid)); continue
        o, t = N.get(oid), N.get(tid)
        if o is None or t is None: continue
        if osl >= len(o.get('outputs', [])) or tsl >= len(t.get('inputs', [])): err.append(('越界', lid)); continue
        ot = o['outputs'][osl].get('type'); tt = t['inputs'][tsl].get('type')
        if ot not in ('*', ty) and tt not in ('*', ty): err.append(('类型', lid, ot, tt, ty))
        if lid not in (o['outputs'][osl].get('links') or []): err.append(('outlinks', lid))
        if t['inputs'][tsl].get('link') != lid: err.append(('inlink', lid))
N = {n['id']: n for n in d['nodes']}
for l in d['links']:
    lid, oid, osl, tid, tsl, ty = unpack(l)
    o, t = N.get(oid), N.get(tid)
    if not o or not t: err.append(('缺失', lid)); continue
    if lid not in (o['outputs'][osl].get('links') or []): err.append(('outlinks', lid))
    if t['inputs'][tsl].get('link') != lid: err.append(('inlink', lid))
print('连线校验:', err if err else '通过')
