# -*- coding: utf-8 -*-
"""修复 视频去水印_LaMa轻量版.json 的「一闪一闪」

根因：子图里每帧独立跑 SAM3_Detect，检测框逐帧微变
      -> LaMa 涂抹区域逐帧跳动 -> 糊块在帧间闪。

改法：把逐帧检测换成 SAM3_VideoTrack（追踪）+ SAM3_TrackToMask，
      全片用同一条追踪出来的遮罩 -> 涂抹区域稳定 -> 不闪。
      接口（frames / what to remove / how sure / grow by / sam3 model / text encoder）保持不变。
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

F = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\视频去水印_LaMa轻量版.json'
with open(F, encoding='utf-8') as f:
    d = json.load(f)

def getlinks(s):
    out = []
    for l in s['links']:
        if isinstance(l, list):
            lid, oid, osl, tid, tsl, ty = l
        else:
            lid, oid, osl, tid, tsl, ty = l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']
        out.append([lid, oid, osl, tid, tsl, ty])
    return out

def setlink(s, lid, new_target=None, new_target_slot=None, new_type=None, drop=False):
    for l in s['links']:
        if isinstance(l, list):
            if l[0] != lid: continue
            if drop:
                s['links'].remove(l); return True
            if new_target is not None: l[3] = new_target
            if new_target_slot is not None: l[4] = new_target_slot
            if new_type is not None: l[5] = new_type
            return True
    return False

changed = []

for s in d['definitions']['subgraphs']:
    if 'every frame' not in s.get('name', ''):
        continue
    N = {n['id']: n for n in s['nodes']}
    det = next((n for n in s['nodes'] if n['type'] == 'SAM3_Detect'), None)
    if det is None:
        continue
    det_id = det['id']
    refine = next(n for n in s['nodes'] if n['type'] == 'AUSBOSS_NODES_RefineMask')
    # 找到指向 SAM3_Detect 的连线
    l_frames = l_model = l_cond = l_thr = l_mask = None
    for l in getlinks(s):
        lid, oid, osl, tid, tsl, ty = l
        if tid != det_id: continue
        name = (N.get(tid, {}).get('inputs') or [{}])[tsl].get('name')
        if name == 'image': l_frames = lid
        elif name == 'model': l_model = lid
        elif name == 'conditioning': l_cond = lid
        elif name == 'threshold': l_thr = lid
    # RefineMask 的 mask 输入来自 SAM3_Detect.masks
    for l in getlinks(s):
        if l[1] == det_id and l[2] == 0 and l[3] == refine['id']:
            l_mask = l[0]
    if not (l_frames and l_model and l_cond and l_thr and l_mask):
        print('  跳过：连线识别不全', l_frames, l_model, l_cond, l_thr, l_mask); continue

    TRACK_ID, MASK_ID = 30, 31
    L_TRACK, L_MASK = 115, 116

    track = {
        "id": TRACK_ID, "type": "SAM3_VideoTrack",
        "pos": [-180, 300], "size": [300, 230],
        "flags": {}, "order": 90, "mode": 0,
        "inputs": [
            {"label": "images", "localized_name": "图像", "name": "images", "type": "IMAGE", "link": l_frames},
            {"label": "model", "localized_name": "model", "name": "model", "type": "MODEL", "link": l_model},
            {"label": "initial_mask", "localized_name": "初始 mask", "name": "initial_mask", "shape": 7, "type": "MASK", "link": None},
            {"label": "conditioning", "localized_name": "条件", "name": "conditioning", "shape": 7, "type": "CONDITIONING", "link": l_cond},
            {"label": "detection_threshold", "localized_name": "检测阈值", "name": "detection_threshold", "type": "FLOAT",
             "widget": {"name": "detection_threshold"}, "link": l_thr},
            {"label": "max_objects", "localized_name": "最大对象数", "name": "max_objects", "type": "INT",
             "widget": {"name": "max_objects"}, "link": None},
            {"label": "detect_interval", "localized_name": "检测间隔", "name": "detect_interval", "type": "INT",
             "widget": {"name": "detect_interval"}, "link": None},
        ],
        "outputs": [{"label": "track_data", "localized_name": "track_data", "name": "track_data",
                     "type": "SAM3_TRACK_DATA", "links": [L_TRACK], "slot_index": 0}],
        "properties": {"Node name for S&R": "SAM3_VideoTrack"},
        "widgets_values": [0.5, 4, 25],
        "title": "SAM3 追踪 (全片一致遮罩)",
    }
    tomask = {
        "id": MASK_ID, "type": "SAM3_TrackToMask",
        "pos": [170, 300], "size": [280, 120],
        "flags": {}, "order": 91, "mode": 0,
        "inputs": [
            {"label": "track_data", "localized_name": "track_data", "name": "track_data",
             "type": "SAM3_TRACK_DATA", "link": L_TRACK},
            {"label": "object_indices", "localized_name": "object_indices", "name": "object_indices",
             "type": "STRING", "widget": {"name": "object_indices"}, "link": None},
        ],
        "outputs": [{"label": "masks", "localized_name": "masks", "name": "masks", "type": "MASK",
                     "links": [L_MASK], "slot_index": 0}],
        "properties": {"Node name for S&R": "SAM3_TrackToMask"},
        "widgets_values": [""],
        "title": "追踪 -> 遮罩 (全部对象并集)",
    }

    # 改指向
    setlink(s, l_frames, new_target=TRACK_ID, new_target_slot=0, new_type='IMAGE')
    setlink(s, l_model, new_target=TRACK_ID, new_target_slot=1, new_type='MODEL')
    setlink(s, l_cond, new_target=TRACK_ID, new_target_slot=3, new_type='CONDITIONING')
    setlink(s, l_thr, new_target=TRACK_ID, new_target_slot=4, new_type='FLOAT')
    setlink(s, l_mask, drop=True)                       # 旧的 masks -> RefineMask
    # 新增两条连线
    s['links'].append([L_TRACK, TRACK_ID, 0, MASK_ID, 0, 'SAM3_TRACK_DATA'])
    s['links'].append([L_MASK, MASK_ID, 0, refine['id'], 0, 'MASK'])
    # RefineMask 的 mask 输入改指新连线
    for i in refine['inputs']:
        if i.get('name') == 'mask':
            i['link'] = L_MASK
    # 移除 SAM3_Detect
    s['nodes'] = [n for n in s['nodes'] if n['id'] != det_id]
    s['nodes'].append(track)
    s['nodes'].append(tomask)
    changed.append('子图「%s」: SAM3_Detect -> SAM3_VideoTrack + SAM3_TrackToMask' % s.get('name'))
    changed.append('  detect_interval=25（每25帧重检测，其余靠追踪）; object_indices 空=全部对象并集')

# 提示词更具体（原来只有 "watermark"），logo 和文字都要覆盖
for n in d['nodes']:
    if n.get('type') == 'AUSBOSS_NODES_Text':
        wv = n.get('widgets_values')
        if isinstance(wv, list) and wv and isinstance(wv[0], str) and wv[0].strip().lower() == 'watermark':
            wv[0] = 'watermark logo and text'
            changed.append('提示词: "watermark" -> "watermark logo and text"')

with open(F, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('已改:')
for c in changed: print('  ', c)
