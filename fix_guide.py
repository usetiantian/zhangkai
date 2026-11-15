import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WD = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
def unpack(l):
    return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']) if isinstance(l, dict) else tuple(l)
def mk(lid, oid, osl, tid, tsl, ty):
    return {'id': lid, 'origin_id': oid, 'origin_slot': osl, 'target_id': tid, 'target_slot': tsl, 'type': ty}

for fn in ['视频去水印_LaMa轻量版.json', '视频去水印_LaMa高质量.json']:
    F = os.path.join(WD, fn)
    if not os.path.exists(F):
        print('跳过(不存在):', fn); continue
    d = json.load(open(F, encoding='utf-8'))
    changed = []
    for s in d['definitions']['subgraphs']:
        N = {n['id']: n for n in s['nodes']}
        rm = [n for n in s['nodes'] if n['type'] == 'AUSBOSS_NODES_RefineMask']
        if not rm: continue
        # 找一个从接口 -10 出来的 frames 来源
        fr = next(((unpack(l)[1], unpack(l)[2]) for l in s['links'] if unpack(l)[1] == -10), None)
        if fr is None: continue
        # 找 guide_image 插槽下标
        for r in rm:
            gi = next((i for i, x in enumerate(r['inputs']) if x.get('name') == 'guide_image'), None)
            if gi is None: continue
            if r['inputs'][gi].get('link') is not None: continue
            nid = max([unpack(l)[0] for l in s['links']] + [0]) + 1
            s['links'].append(mk(nid, fr[0], fr[1], r['id'], gi, 'IMAGE'))
            r['inputs'][gi]['link'] = nid
            changed.append('%s: guide_image <- frames (link %d)' % (s.get('name'), nid))
        # 重建 outputs.links
        for n in s['nodes']:
            for o in n.get('outputs') or []: o['links'] = None
        for l in s['links']:
            lid, oid, osl, tid, tsl, ty = unpack(l)
            o = N.get(oid)
            if not o or osl >= len(o.get('outputs') or []): continue
            o['outputs'][osl]['links'] = o['outputs'][osl].get('links') or []
            o['outputs'][osl]['links'].append(lid)
        for n in s['nodes']:
            for o in n.get('outputs') or []:
                if not o.get('links'): o['links'] = None
    json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('%s: %s' % (fn, changed if changed else '无需修改'))
