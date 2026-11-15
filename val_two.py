import json, os, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
info = json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=40))
WD = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
def unpack(l):
    return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']) if isinstance(l, dict) else tuple(l)
for fn in ['视频去水印_LaMa轻量版.json', '视频去水印_LaMa高质量.json']:
    F = os.path.join(WD, fn)
    d = json.load(open(F, encoding='utf-8'))
    err = []
    for s in d['definitions']['subgraphs']:
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
    print('%-34s %s' % (fn, err if err else '连线全部正确'))
    # 顺便打印各子图接口定义，确认 guide_image 接的源类型
    for s in d['definitions']['subgraphs']:
        ins = [(i.get('name'), i.get('type')) for i in s.get('inputs', [])]
        N = {n['id']: n for n in s['nodes']}
        rm = next((n for n in s['nodes'] if n['type'] == 'AUSBOSS_NODES_RefineMask'), None)
        if rm:
            gi = next((i for i, x in enumerate(rm['inputs']) if x.get('name') == 'guide_image'), None)
            lk = rm['inputs'][gi].get('link')
            src = None
            for l in s['links']:
                if unpack(l)[0] == lk:
                    src = unpack(l)[1:]
            print('   子图 %-24s 接口=%s' % (s.get('name'), ins))
            print('      guide_image <- %s' % (src,))
