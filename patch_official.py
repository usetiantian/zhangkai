# -*- coding: utf-8 -*-
"""把官方 Character-Swap 工作流改成适配本机的版本"""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

F = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\H3角色替换_CharacterSwap_官方.json'
with open(F, encoding='utf-8') as f:
    d = json.load(f)

REPL = {
    # 本机实际文件名（官方示例用的是 _768p_comfyui 变体，本机是非 768p 版）
    'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors':
        'minimax_h3_fl2v_turbo_8step_v1.0_bf16.safetensors',
    # 官方示例引用的是 v1 的 eval 权重；换成官方 README 推荐的 V1.5
    'h3-v2-challenge-eval-20261013/v2-1000.safetensors':
        'h3_character_swap_v1.5.safetensors',
}

changed = []
for n in d.get('nodes', []):
    wv = n.get('widgets_values')
    if not isinstance(wv, list):
        continue
    for i, v in enumerate(wv):
        if isinstance(v, str) and v in REPL:
            wv[i] = REPL[v]
            changed.append('%s : %s -> %s' % (n.get('type'), v, REPL[v]))
    # MarkdownNote -> AUSBOSS_NODES_WorkflowNote（后端未注册 MarkdownNote，会多报一个缺失包）
    if n.get('type') == 'MarkdownNote':
        n['type'] = 'AUSBOSS_NODES_WorkflowNote'
        n['properties'] = {"cnr_id": "ausboss-nodes", "ver": "2.2.0",
                            "Node name for S&R": "AUSBOSS_NODES_WorkflowNote"}
        for i in n.get('inputs', []):
            if i.get('name') == 'text':
                i['name'] = 'note'
                i['localized_name'] = '说明'
                i['widget'] = {'name': 'note'}
        changed.append('MarkdownNote -> AUSBOSS_NODES_WorkflowNote')

with open(F, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('已改 %d 处:' % len(changed))
for c in changed:
    print('  ', c)
