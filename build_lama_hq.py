# -*- coding: utf-8 -*-
"""新建「视频去水印_LaMa高质量」：按遮罩逐帧裁剪 -> 512 -> LaMa -> 逐帧贴回"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SRC = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\视频去水印_LaMa轻量版.json'
DST = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\视频去水印_LaMa高质量.json'
d = json.load(open(SRC, encoding='utf-8'))

CROP_ID, UNCROP_ID = 32, 33
L_CROP_IMGS, L_CROP_MASKS, L_LAMA_IMG, L_LAMA_MASK = 118, 119, 120, 121
L_UNC_SRC, L_UNC_MASK, L_UNC_BBOX, L_UNC_DEST = 122, 123, 124, 125

def unpack(l):
    return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']) if isinstance(l, dict) else tuple(l)
def mk(lid, oid, osl, tid, tsl, ty):
    return {'id': lid, 'origin_id': oid, 'origin_slot': osl, 'target_id': tid, 'target_slot': tsl, 'type': ty}

for s in d['definitions']['subgraphs']:
    if 'every frame' not in s.get('name', ''): continue
    lama = next(n for n in s['nodes'] if n['type'] == 'AUSBOSS_NODES_LaMaInpaint')
    def link_into(name):
        for l in s['links']:
            lid, oid, osl, tid, tsl, ty = unpack(l)
            if tid == lama['id'] and (lama['inputs'] or [{}])[tsl].get('name') == name:
                return lid, oid, osl
        return None, None, None
    l_frames, o_frames, s_frames = link_into('image')
    l_mask, o_mask, s_mask = link_into('mask')
    l_out = next(unpack(l)[0] for l in s['links'] if unpack(l)[3] == -20)
    if not (l_frames and l_mask and l_out):
        print('跳过'); continue

    crop = {"id": CROP_ID, "type": "ImageCropByMaskAndResize", "pos": [700, 320], "size": [350, 240],
        "flags": {}, "order": 80, "mode": 0,
        "inputs": [
            {"label": "image", "name": "image", "type": "IMAGE", "link": l_frames},
            {"label": "mask", "name": "mask", "type": "MASK", "link": l_mask},
            {"label": "base_resolution", "name": "base_resolution", "type": "INT", "widget": {"name": "base_resolution"}, "link": None},
            {"label": "padding", "name": "padding", "type": "INT", "widget": {"name": "padding"}, "link": None},
            {"label": "min_crop_resolution", "name": "min_crop_resolution", "type": "INT", "widget": {"name": "min_crop_resolution"}, "link": None},
            {"label": "max_crop_resolution", "name": "max_crop_resolution", "type": "INT", "widget": {"name": "max_crop_resolution"}, "link": None}],
        "outputs": [
            {"label": "images", "name": "images", "type": "IMAGE", "links": [L_CROP_IMGS], "slot_index": 0},
            {"label": "masks", "name": "masks", "type": "MASK", "links": [L_CROP_MASKS, L_UNC_MASK], "slot_index": 1},
            {"label": "bbox", "name": "bbox", "type": "BBOX", "links": [L_UNC_BBOX], "slot_index": 2}],
        "properties": {"Node name for S&R": "ImageCropByMaskAndResize", "cnr_id": "comfyui-kjnodes"},
        "widgets_values": [512, 24, 128, 512], "title": "按遮罩逐帧裁剪并缩放到512 (LaMa甜区)"}
    uncrop = {"id": UNCROP_ID, "type": "ImageUncropByMask", "pos": [1120, 320], "size": [350, 230],
        "flags": {}, "order": 82, "mode": 0,
        "inputs": [
            {"label": "destination", "name": "destination", "type": "IMAGE", "link": L_UNC_DEST},
            {"label": "source", "name": "source", "type": "IMAGE", "link": L_UNC_SRC},
            {"label": "mask", "name": "mask", "type": "MASK", "link": L_UNC_MASK},
            {"label": "bbox", "name": "bbox", "type": "BBOX", "link": L_UNC_BBOX}],
        "outputs": [{"label": "image", "name": "image", "type": "IMAGE", "links": [l_out], "slot_index": 0}],
        "properties": {"Node name for S&R": "ImageUncropByMask", "cnr_id": "comfyui-kjnodes"},
        "widgets_values": [], "title": "贴回原帧 (逐帧)"}

    # 老连线改为指向 crop；LaMa 输出改指 uncrop.source；子图输出改由 uncrop 产生
    for l in s['links']:
        lid, oid, osl, tid, tsl, ty = unpack(l)
        if lid == l_frames:
            if isinstance(l, dict): l['target_id'], l['target_slot'], l['type'] = CROP_ID, 0, 'IMAGE'
            else: l[3], l[4], l[5] = CROP_ID, 0, 'IMAGE'
        elif lid == l_mask:
            if isinstance(l, dict): l['target_id'], l['target_slot'], l['type'] = CROP_ID, 1, 'MASK'
            else: l[3], l[4], l[5] = CROP_ID, 1, 'MASK'
        elif lid == l_out:
            if isinstance(l, dict): l['origin_id'], l['origin_slot'], l['type'] = UNCROP_ID, 0, 'IMAGE'
            else: l[1], l[2], l[5] = UNCROP_ID, 0, 'IMAGE'
    # LaMa 的输入改指 crop 的输出
    for i in lama['inputs']:
        if i.get('name') == 'image': i['link'] = L_LAMA_IMG
        if i.get('name') == 'mask': i['link'] = L_LAMA_MASK
    lama['title'] = 'LaMa 修复 (在512小图上)'
    # LaMa 原来的输出链接(指向子图输出)已经被改走，这里补一条 LaMa -> uncrop.source
    s['links'].append(mk(L_CROP_IMGS, CROP_ID, 0, lama['id'], 0, 'IMAGE'))
    s['links'].append(mk(L_CROP_MASKS, CROP_ID, 1, lama['id'], 1, 'MASK'))
    s['links'].append(mk(L_UNC_SRC, lama['id'], 0, UNCROP_ID, 1, 'IMAGE'))
    s['links'].append(mk(L_UNC_MASK, CROP_ID, 1, UNCROP_ID, 2, 'MASK'))
    s['links'].append(mk(L_UNC_BBOX, CROP_ID, 2, UNCROP_ID, 3, 'BBOX'))
    s['links'].append(mk(L_UNC_DEST, o_frames, s_frames, UNCROP_ID, 0, 'IMAGE'))
    # LaMa 的输出列表要加上 L_UNC_SRC；原来它连着子图输出
    for i in lama['outputs']:
        lk = i.get('links') or []
        lk = [x for x in lk if x != l_out]
        if i.get('name') == 'IMAGE': lk.append(L_UNC_SRC)
        i['links'] = lk or None
    for i in s.get('outputs', []):
        if i.get('name') == 'clean frames': i['linkIds'] = [l_out]
    s['nodes'].append(crop); s['nodes'].append(uncrop)
    print('子图「%s」已改造' % s.get('name'))

d['id'] = 'uuid-lama-hq-0001'
json.dump(d, open(DST, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已生成:', DST)
