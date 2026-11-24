# -*- coding: utf-8 -*-
BS = chr(92)
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
t = open(F, encoding="utf-8").read()

# 1) global_prompt 去掉硬编码的 Picture 1 绑定
old = ('    "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带。<Picture 1> 为林问的形象参考，"{BS}n'
       '    "保持相同的面部特征、发型与服装。{BS}n"').replace("{BS}", BS)
new = ('    "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带。{BS}n"').replace("{BS}", BS)
assert old in t, "global_prompt pattern missing"
t = t.replace(old, new)

# 2) build_segments 支持 only
old2 = '''def build_segments(sb, pairs):
    segs = []
    for sh in sb["shots"]:
        p = pairs.get(sh["idx"], [])
        segs.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                    duration=SHOT_DUR,
                                    refs=[f for _, f in p]))
    return segs'''
new2 = '''def build_segments(sb, pairs, only=None):
    """only=None 全开；only=[3] 只跑第 3 镜（其余 disabled，段号不变）。"""
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
assert old2 in t, "build_segments missing"
t = t.replace(old2, new2)

t = t.replace('skip_tts=False, log=print, proj=None):',
              'skip_tts=False, log=print, proj=None, only_shots=None):')
t = t.replace('    segs = build_segments(sb, pairs)', '    segs = build_segments(sb, pairs, only=only_shots)')
t = t.replace('    if _shot_files(proj, len(segs), "一次采样"):',
              '    if not only_shots and _shot_files(proj, len(segs), "一次采样"):')
t = t.replace('        if _shot_files(proj, len(sb["shots"]), "二次采样"):',
              '        if not only_shots and _shot_files(proj, len(sb["shots"]), "二次采样"):')

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
assert old4 in t, "二采 missing"
t = t.replace(old4, new4)

t = t.replace('    ap.add_argument("--force-storyboard", action="store_true")',
              '    ap.add_argument("--force-storyboard", action="store_true")\n'
              '    ap.add_argument("--only-shots", default=None, help="只重跑指定镜号, 逗号分隔")')
old6 = '''                                 skip_tts=a.no_tts), ensure_ascii=False))'''
new6 = '''                                 skip_tts=a.no_tts, only_shots=only), ensure_ascii=False))'''
assert old6 in t
t = t.replace(old6, new6)
t = t.replace('    for e in (a.ep or [1]):',
              '    only = None\n'
              '    if a.only_shots:\n'
              '        only = [int(x) for x in a.only_shots.split(",") if x.strip()]\n'
              '    for e in (a.ep or [1]):')
open(F, "w", encoding="utf-8").write(t)
print("produce_ep.py patched OK")
