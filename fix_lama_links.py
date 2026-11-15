# -*- coding: utf-8 -*-
"""修正：上一个脚本按 list 格式改连线，但本文件的 links 是 dict 格式，
所以 4 条连线和删除操作都没生效。这里按 dict 格式补上。"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

F = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\视频去水印_LaMa轻量版.json'
with open(F, encoding='utf-8') as f:
    d = json.load(f)

TRACK_ID, MASK_ID = 30, 31
# link_id -> (新 target, 新 target_slot)
RETARGET = {
    101: (TRACK_ID, 0),   # frames  -> VideoTrack.images
    106: (TRACK_ID, 1),   # model   -> VideoTrack.model
    107: (TRACK_ID, 3),   # cond    -> VideoTrack.conditioning
    109: (TRACK_ID, 4),   # how sure -> VideoTrack.detection_threshold
}
DROP = {110}             # 旧的 SAM3_Detect.masks -> RefineMask.mask

changed = []
for s in d['definitions']['subgraphs']:
    if 'every frame' not in s.get('name', ''):
        continue
    newlinks = []
    for l in s['links']:
        if isinstance(l, dict):
            lid = l['id']
            if lid in DROP:
                changed.append('删除 L%d (SAM3_Detect.masks -> RefineMask.mask)' % lid)
                continue
            if lid in RETARGET:
                t, ts = RETARGET[lid]
                changed.append('L%d: target %s.slot%d -> %s.slot%d' % (lid, l['target_id'], l['target_slot'], t, ts))
                l['target_id'] = t
                l['target_slot'] = ts
            newlinks.append(l)
        else:
            lid = l[0]
            if lid in DROP:
                changed.append('删除 L%d' % lid); continue
            if lid in RETARGET:
                t, ts = RETARGET[lid]
                changed.append('L%d: target %s.slot%d -> %s.slot%d' % (lid, l[3], l[4], t, ts))
                l[3] = t; l[4] = ts
            newlinks.append(l)
    s['links'] = newlinks
    # RefineMask 的 mask 输入指向新连线 116
    for n in s['nodes']:
        if n['type'] == 'AUSBOSS_NODES_RefineMask':
            for i in n['inputs']:
                if i.get('name') == 'mask':
                    i['link'] = 116
    # 保证 SAM3_Detect 已移除
    before = len(s['nodes'])
    s['nodes'] = [n for n in s['nodes'] if n['type'] != 'SAM3_Detect']
    if before != len(s['nodes']):
        changed.append('移除 SAM3_Detect 节点')

with open(F, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('已修正:')
for c in changed: print('  ', c)
