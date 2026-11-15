import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
F = os.path.join(r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows', '视频去水印_LaMa高质量.json')
d = json.load(open(F, encoding='utf-8'))
def unpack(l):
    return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']) if isinstance(l, dict) else tuple(l)

# LaMa 的输入指向：crop.images / crop.masks 承载它们
for s in d['definitions']['subgraphs']:
    N = {n['id']: n for n in s['nodes']}
    # 找 crop->lama 和 lama->uncrop 的链接 id
    crop = next((n for n in s['nodes'] if n['type'] == 'ImageCropByMaskAndResize'), None)
    uncrop = next((n for n in s['nodes'] if n['type'] == 'ImageUncropByMask'), None)
    lama = next((n for n in s['nodes'] if n['type'] == 'AUSBOSS_NODES_LaMaInpaint'), None)
    if not (crop and uncrop and lama): continue
    for l in s['links']:
        lid, oid, osl, tid, tsl, ty = unpack(l)
        if tid == lama['id'] and osl == 0 and oid == crop['id']:
            for i in lama['inputs']:
                if i.get('name') == 'image': i['link'] = lid
        if tid == lama['id'] and osl == 1 and oid == crop['id']:
            for i in lama['inputs']:
                if i.get('name') == 'mask': i['link'] = lid
    # 重建所有节点的 outputs.links
    for n in s['nodes']:
        for oi, o in enumerate(n.get('outputs') or []):
            o['links'] = None
    for l in s['links']:
        lid, oid, osl, tid, tsl, ty = unpack(l)
        o = N.get(oid)
        if not o or osl >= len(o.get('outputs') or []): continue
        outs = o['outputs']
        outs[osl]['links'] = outs[osl].get('links') or []
        outs[osl]['links'].append(lid)
    for n in s['nodes']:
        for o in n.get('outputs') or []:
            if not o.get('links'): o['links'] = None
# 顶层同样重建
N = {n['id']: n for n in d['nodes']}
for n in d['nodes']:
    for o in n.get('outputs') or []: o['links'] = None
for l in d['links']:
    lid, oid, osl, tid, tsl, ty = unpack(l)
    o = N.get(oid)
    if not o or osl >= len(o.get('outputs') or []): continue
    o['outputs'][osl]['links'] = o['outputs'][osl].get('links') or []
    o['outputs'][osl]['links'].append(lid)
for n in d['nodes']:
    for o in n.get('outputs') or []:
        if not o.get('links'): o['links'] = None
json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已重建 outputs.links')
