# -*- coding: utf-8 -*-
"""升级歌曲制作台：暴露时长/种子 + 加手写ABC曲谱入口"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WD = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
F = os.path.join(WD, '歌曲制作台_A_YuE2选曲谱.json')
d = json.load(open(F, encoding='utf-8'))
INST = '59dddde1-2d83-4b6e-9c71-1e5cb2d823d6'
def unpack(l):
    return (l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']) if isinstance(l, dict) else tuple(l)

for n in d['nodes']:
    if n.get('type') != INST: continue
    have = {i['name'] for i in n.get('inputs', [])}
    wv = n['widgets_values']
    if 'max_duration' not in have:
        n['inputs'].append({"label": "出歌时长(秒)", "name": "max_duration", "type": "FLOAT",
                           "widget": {"name": "max_duration"}, "link": None})
        wv.append(120.0)
    if 'seed' not in have:
        n['inputs'].append({"label": "种子", "name": "seed", "type": "INT",
                           "widget": {"name": "seed"}, "link": None})
        wv.append(42)
    print('  顶层 inputs:', [i['name'] for i in n['inputs']])

for s in d.get('definitions', {}).get('subgraphs', []):
    N = {n['id']: n for n in s['nodes']}
    abc_node = next((n for n in s['nodes'] if n['type'] == 'SheetSage2AudioToABC'), None)
    music_node = next((n for n in s['nodes'] if n['type'] == 'YuE2GenerateMusic'), None)
    if not (abc_node and music_node): continue
    old_link = None
    for l in s['links']:
        lid, oid, osl, tid, tsl, ty = unpack(l)
        if tid != music_node['id']: continue
        tn = (music_node.get('inputs') or [{}])[tsl].get('name')
        if tn == 'abc':
            old_link = l
    if old_link is None:
        print('  没找到 abc 连线'); continue
    L_ABC, L_SW2ABC = 301, 302
    SW_ID, TXT_ID = 60, 61
    if isinstance(old_link, dict):
        old_link['target_id'] = SW_ID; old_link['target_slot'] = 1; old_link['type'] = 'STRING'
    else:
        old_link[3], old_link[4], old_link[5] = SW_ID, 1, 'STRING'
    s['nodes'].append({
        "id": SW_ID, "type": "ComfySwitchNode", "pos": [430, 700], "size": [300, 140],
        "flags": {}, "order": 200, "mode": 0,
        "inputs": [
            {"label": "switch", "name": "switch", "type": "BOOLEAN", "widget": {"name": "switch"}, "link": None},
            {"label": "on_false", "name": "on_false", "type": "STRING", "widget": {"name": "on_false"}, "link": None},
            {"label": "on_true", "name": "on_true", "type": "STRING", "widget": {"name": "on_true"}, "link": None}],
        "outputs": [{"label": "output", "name": "output", "type": "STRING", "links": [L_SW2ABC], "slot_index": 0}],
        "properties": {"Node name for S&R": "ComfySwitchNode"},
        "widgets_values": [False],
        "title": "曲谱来源: False=自动转ABC  True=用手写ABC"})
    s['nodes'].append({
        "id": TXT_ID, "type": "PrimitiveStringMultiline", "pos": [130, 700], "size": [280, 200],
        "flags": {}, "order": 201, "mode": 0,
        "inputs": [{"label": "value", "name": "value", "type": "STRING", "widget": {"name": "value"}, "link": None}],
        "outputs": [{"label": "value", "name": "value", "type": "STRING", "links": [L_ABC], "slot_index": 0}],
        "properties": {"Node name for S&R": "PrimitiveStringMultiline"},
        "widgets_values": [""],
        "title": "手写 ABC 曲谱(留空则不用)"})
    s['links'].append({'id': L_ABC, 'origin_id': TXT_ID, 'origin_slot': 0, 'target_id': SW_ID, 'target_slot': 2, 'type': 'STRING'})
    s['links'].append({'id': L_SW2ABC, 'origin_id': SW_ID, 'origin_slot': 0, 'target_id': music_node['id'],
                       'target_slot': 3, 'type': 'STRING'})
    for i in music_node['inputs']:
        if i.get('name') == 'abc': i['link'] = L_SW2ABC
    for n in s['nodes']:
        for o in n.get('outputs') or []: o['links'] = None
    for l in s['links']:
        lid, oid, osl, tid, tsl, ty = unpack(l)
        o = next((x for x in s['nodes'] if x['id'] == oid), None)
        if not o or osl >= len(o.get('outputs') or []): continue
        o['outputs'][osl]['links'] = o['outputs'][osl].get('links') or []
        o['outputs'][osl]['links'].append(lid)
    for n in s['nodes']:
        for o in n.get('outputs') or []:
            if not o.get('links'): o['links'] = None
    print('  子图: 已加 ComfySwitchNode + PrimitiveStringMultiline')

json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已更新:', F)
