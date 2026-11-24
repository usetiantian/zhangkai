# -*- coding: utf-8 -*-
"""修 视频修补.json：模型文件名对齐本机 + 默认视频 + 注释节点换后端已注册的"""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

F = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\视频修补.json'
with open(F, encoding='utf-8') as f:
    d = json.load(f)

REPL = {
    # 本机有 fp8 版，省 11GB 下载
    't5xxl_fp16.safetensors': 't5xxl_fp8_e4m3fn.safetensors',
    # 本机只有 bf16 / fp32 版
    'cogvideox_vae.safetensors': 'cogvideox_vae_bf16.safetensors',
    # 官方模板的示例视频本机没有
    'snowboarder.mp4': '抖音202695-416805.mp4',
}

changed = []

def fix_loaders(nodes):
    for n in nodes:
        wv = n.get('widgets_values')
        if not isinstance(wv, list):
            continue
        for i, v in enumerate(wv):
            if isinstance(v, str) and v in REPL:
                wv[i] = REPL[v]
                changed.append('%s: %s -> %s' % (n.get('type'), v, REPL[v]))

fix_loaders(d.get('nodes', []))
for s in d.get('definitions', {}).get('subgraphs', []):
    fix_loaders(s.get('nodes', []))

# VOID 正向提示词：原模板是雪山滑板，改成与本机测试片匹配
for s in d.get('definitions', {}).get('subgraphs', []):
    for n in s.get('nodes', []):
        if n.get('type') == 'CLIPTextEncode':
            wv = n.get('widgets_values')
            if isinstance(wv, list) and wv and isinstance(wv[0], str) and 'Skateboard' in wv[0]:
                wv[0] = 'a person indoors, clean background'
                changed.append('CLIPTextEncode: VOID 正向提示词 -> 与本机测试片匹配')

# MarkdownNote -> AUSBOSS_NODES_WorkflowNote（后端未注册 MarkdownNote，会多报一个缺失包）
def fix_notes(nodes):
    for n in nodes:
        if n.get('type') != 'MarkdownNote':
            continue
        wv = n.get('widgets_values')
        text = wv[0] if isinstance(wv, list) and wv else ''
        title = '使用说明'
        for line in text.split('\n'):
            s = line.strip().lstrip('#').strip()
            if s:
                title = s[:48]
                break
        n['type'] = 'AUSBOSS_NODES_WorkflowNote'
        n['properties'] = {"cnr_id": "ausboss-nodes", "ver": "2.2.0",
                            "Node name for S&R": "AUSBOSS_NODES_WorkflowNote"}
        for i in n.get('inputs', []):
            if i.get('name') == 'text':
                i['name'] = 'note'
                i['localized_name'] = '说明'
                i['widget'] = {'name': 'note'}
        n['widgets_values'] = [json.dumps({
            "v": 1, "title": title, "subtitle": "", "author": "ComfyUI 官方模板",
            "layout": "card", "accent": "", "body": text,
        }, ensure_ascii=False)]
        changed.append('MarkdownNote -> AUSBOSS_NODES_WorkflowNote (%s)' % title[:24])

fix_notes(d.get('nodes', []))
for s in d.get('definitions', {}).get('subgraphs', []):
    fix_notes(s.get('nodes', []))

with open(F, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('已改 %d 处:' % len(changed))
for c in changed:
    print('  ', c)
