# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
t = open(F, encoding="utf-8").read()

# 1) global_prompt 不能再硬编码 "<Picture 1> = 林问"，否则与镜头级 Picture 绑定冲突
old = ('    "主角林问：16岁中国少年，身形清瘦单薄，眉清目秀神情执拗，黑发束成简单发髻，"\n'
       '    "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带。<Picture 1> 为林问的形象参考，"\n'
       '    "保持相同的面部特征、发型与服装。\n"')
new = ('    "主角林问：16岁中国少年，身形清瘦单薄，眉清目秀神情执拗，黑发束成简单发髻，"\n'
       '    "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带。\n"')
assert old in t, "global_prompt pattern missing"
t = t.replace(old, new)

# 2) build_segments 支持只启用指定镜头（保持段号，用于单镜重跑）
old2 = '''def build_segments(sb, pairs):
    segs = []
    for sh in sb["shots"]:
        p = pairs.get(sh["idx"], [])
        segs.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                    duration=SHOT_DUR,
                                    refs=[f for _, f in p]))
    return segs'''
new2 = '''def build_segments(sb, pairs, only=None):
    """only=None 表示全开；only=[3] 表示只跑第 3 镜（其余 disabled，段号保持不变）。"""
    segs = []
    for sh in sb["shots"]:
        p = pairs.get(sh["idx"], [])
        s = H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                            duration=SHOT_DUR,
                            refs=[f for _, f in p])
        if only and sh["idx"] not in only:
            s["enabled"] = False
        segs.append(s)
    return segs'''
assert old2 in t, "build_segments pattern missing"
t = t.replace(old2, new2)

# 3) produce() 接受 only_shots
t = t.replace('skip_tts=False, log=print, proj=None):',
              'skip_tts=False, log=print, proj=None, only_shots=None):')
t = t.replace('    segs = build_segments(sb, pairs)', '    segs = build_segments(sb, pairs, only=only_shots)')

# 4) 二采的段构建也要支持 only
old4 = '''            segs2 = []
            for sh in sb["shots"]:
                p = pairs.get(sh["idx"], [])
                segs2.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                             duration=SHOT_DUR, refs=[f for _, f in p],
                                             second=H.DEFAULT_SECOND, first_pass_version=2))'''
new4 = '''            segs2 = []
            for sh in sb["shots"]:
                p = pairs.get(sh["idx"], [])
                s2 = H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                    duration=SHOT_DUR, refs=[f for _, f in p],
                                    second=H.DEFAULT_SECOND, first_pass_version=2)
                if only_shots and sh["idx"] not in only_shots:
                    s2["enabled"] = False
                segs2.append(s2)'''
assert old4 in t, "二采 pattern missing"
t = t.replace(old4, new4)

# 5) 续跑判断要考虑只跑部分镜头
t = t.replace('    if _shot_files(proj, len(segs), "一次采样"):',
              '    if not only_shots and _shot_files(proj, len(segs), "一次采样"):')
t = t.replace('        if _shot_files(proj, len(sb["shots"]), "二次采样"):',
              '        if not only_shots and _shot_files(proj, len(sb["shots"]), "二次采样"):')

# 6) CLI 加 --only-shots
t = t.replace('    ap.add_argument("--force-storyboard", action="store_true")',
              '    ap.add_argument("--force-storyboard", action="store_true")\n'
              '    ap.add_argument("--only-shots", default=None, help="只重跑指定镜号, 逗号分隔")')
t = t.replace('''    for e in (a.ep or [1]):
        print(json.dumps(produce(e, quality=a.quality, tts_backend=a.tts,
                                 force_storyboard=a.force_storyboard,
                                 skip_tts=a.no_tts), ensure_ascii=False))''',
              '''    only = None
    if a.only_shots:
        only = [int(x) for x in a.only_shots.split(",") if x.strip()]
    for e in (a.ep or [1]):
        print(json.dumps(produce(e, quality=a.quality, tts_backend=a.tts,
                                 force_storyboard=a.force_storyboard,
                                 skip_tts=a.no_tts, only_shots=only), ensure_ascii=False))''')
open(F, "w", encoding="utf-8").write(t)
print("produce_ep.py: Picture 冲突已修 + 单镜重跑已加")
