# -*- coding: utf-8 -*-
"""构建「歌曲制作台」——基于官方 YuE2 Music Cover 模板，中文化 + 加手动ABC曲谱入口"""
import json, os, sys, copy
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WD = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
SRC = r'C:\Users\87999\claude-workspace\tpl_yue2_cover.json'
OUT = os.path.join(WD, '歌曲制作台_A_YuE2选曲谱.json')

d = json.load(open(SRC, encoding='utf-8'))
INST = '59dddde1-2d83-4b6e-9c71-1e5cb2d823d6'

# 1) 中文标题
for n in d['nodes']:
    if n.get('type') == INST:
        n['title'] = '歌曲制作台 (YuE2)'
    if n.get('type') == 'LoadAudio':
        n['title'] = '参考曲子 (选曲谱: 放你的歌; 留默认样例也行)'
    if n.get('type') == 'SaveAudioAdvanced':
        n['title'] = '保存歌曲'
        n['widgets_values'][0] = 'audio/歌曲制作台'

# 2) 默认的风格/音色描述 + 歌词（中文示例，可直接改）
for n in d['nodes']:
    if n.get('type') != INST: continue
    wv = n['widgets_values']
    wv[0] = ('Mandarin pop ballad, warm female vocal, breathy and intimate, 88 BPM, '
              'C major, soft piano intro, warm strings, gentle drums, emotional and nostalgic, '
              'clear vocal in the mix')
    wv[1] = ('[Intro]\n夜色落在窗台上\n风把灯火轻轻摇\n\n'
             '[Verse]\n街灯一盏一盏亮起\n呼吸慢过了心跳\n你的名字还在风里\n\n'
             '[Chorus]\n我们还在原地\n等一场雨停\n把所有没说的\n唱成这首歌\n\n'
             '[Bridge]\n如果时间能倒退\n我还想再看你一眼\n\n'
             '[Chorus]\n我们还在原地\n等一场雨停\n把所有没说的\n唱成这首歌\n\n'
             '[Outro]\n夜色落在窗台上\n风把灯火轻轻摇')

# 3) 子图内部节点中文标题
TITLES = {
    'CheckpointLoaderSimple': '加载 YuE2 模型',
    'AudioEncoderLoader': '加载 SheetSage2 音频编码器',
    'SheetSage2AudioToABC': '参考音频 -> ABC 曲谱',
    'YuE2GenerateMusic': '按曲谱+歌词生成',
    'EmptyYuE2LatentAudio': '音频潜空间',
    'KSampler': '采样',
    'VAEDecodeAudio': '解码音频',
    'ConditioningZeroOut': '负向条件',
    'SeedNode': '随机种子',
}
for s in d.get('definitions', {}).get('subgraphs', []):
    for n in s['nodes']:
        if n.get('type') in TITLES:
            n['title'] = TITLES[n['type']]

# 4) 加一个中文说明卡
note = {
    "id": 900, "type": "AUSBOSS_NODES_WorkflowNote",
    "pos": [-700, 700], "size": [520, 560],
    "flags": {}, "order": 90, "mode": 0,
    "inputs": [], "outputs": [],
    "properties": {"cnr_id": "ausboss-nodes", "ver": "2.2.0",
                   "Node name for S&R": "AUSBOSS_NODES_WorkflowNote"},
    "widgets_values": [json.dumps({
        "v": 1,
        "title": "歌曲制作台 (YuE2)",
        "subtitle": "选曲谱 + 选声音 + 加歌词 = 完整一首歌",
        "author": "ComfyUI 官方模板 + CC 整理",
        "layout": "card", "accent": "",
        "body": (
            "## 三个可填的地方\n\n"
            "**① 风格/音色框**（实例节点第一个文本）\n"
            "写清楚歌手音色和编曲，例如：\n"
            "`warm female vocal, breathy, 88 BPM, C major, soft piano, strings`\n"
            "→ 这就是「选声音」\n\n"
            "**② 歌词框**（实例节点第二个文本）\n"
            "用段落标签分段，模型会按结构编曲：\n"
            "`[Intro] [Verse] [Chorus] [Bridge] [Outro]`\n"
            "→ 这就是「加歌词」\n\n"
            "**③ 参考曲子**（LoadAudio）\n"
            "放一段你有旋律的音频，SheetSage2 会转成 ABC 曲谱，\n"
            "YuE2 保留这个旋律、换上你的歌词和人声。\n"
            "→ 这就是「选曲谱」\n\n"
            "---\n\n"
            "## 出歌时长\n"
            "子图里 max_duration 默认 360 秒（6 分钟）。\n"
            "想要短歌就改小，注意歌词越长生成越久。\n\n"
            "## 模型\n"
            "- checkpoints/yue2_3b_int8_convrot.safetensors\n"
            "- audio_encoders/sheetsage2_bf16.safetensors\n\n"
            "## 想要 BPM/调式/拍号 精确控制？\n"
            "改用 ACE-Step 1.5 那条线（另一份工作流），\n"
            "它有独立的 bpm / keyscale / timesignature 参数。"
        ),
    }, ensure_ascii=False)],
    "title": "使用说明",
}
d['nodes'].append(note)
d['id'] = 'uuid-music-studio-yue2'

json.dump(d, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已生成:', OUT)
print('顶层节点:', len(d['nodes']))
