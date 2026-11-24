# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
lines = open(F, encoding="utf-8").read().split(chr(10))
out = []
i = 0
removed = 0
while i < len(lines):
    ln = lines[i]
    if "为林问的形象参考" in ln:
        # 本行保留前半（去掉 <Picture 1> ... 引用），下一行若为"保持相同..."则一并删掉
        idx = ln.find("<Picture 1>")
        if idx >= 0:
            ln = ln[:idx].rstrip().rstrip(",") + ","
        out.append(ln)
        if i + 1 < len(lines) and "保持相同的面部特征" in lines[i + 1]:
            i += 2
            removed += 1
            continue
        i += 1
        removed += 1
        continue
    out.append(ln)
    i += 1
t = chr(10).join(out)

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
if old2 in t:
    t = t.replace(old2, new2)
    print("build_segments updated")
t = t.replace('skip_tts=False, log=print, proj=None):',
              'skip_tts=False, log=print, proj=None, only_shots=None):')
t = t.replace('    segs = build_segments(sb, pairs)', '    segs = build_segments(sb, pairs, only=only_shots)')
t = t.replace('    if _shot_files(proj, len(segs), "一次采样"):',
              '    if not only_shots and _shot_files(proj, len(segs), "一次采样"):')
t = t.replace('        if _shot_files(proj, len(sb["shots"]), "二次采样"):',
              '        if not only_shots and _shot_files(proj, len(sb["shots"]), "二次采样"):')
old4 = '''                segs2.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                             duration=SHOT_DUR, refs=[f for _, f in p],
                                             second=H.DEFAULT_SECOND, first_pass_version=2))'''
new4 = '''                s2 = H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                    duration=SHOT_DUR, refs=[f for _, f in p],
                                    second=H.DEFAULT_SECOND, first_pass_version=2)
                if only_shots and sh["idx"] not in only_shots:
                    s2["enabled"] = False
                segs2.append(s2)'''
if old4 in t:
    t = t.replace(old4, new4)
    print("二采 updated")
t = t.replace('    ap.add_argument("--force-storyboard", action="store_true")',
              '    ap.add_argument("--force-storyboard", action="store_true")\n'
              '    ap.add_argument("--only-shots", default=None, help="只重跑指定镜号, 逗号分隔")')
t = t.replace('                                 skip_tts=a.no_tts), ensure_ascii=False))',
              '                                 skip_tts=a.no_tts, only_shots=only), ensure_ascii=False))')
t = t.replace('    for e in (a.ep or [1]):',
              '    only = None\n'
              '    if a.only_shots:\n'
              '        only = [int(x) for x in a.only_shots.split(",") if x.strip()]\n'
              '    for e in (a.ep or [1]):')
open(F, "w", encoding="utf-8").write(t)
print("removed Picture-1-clause lines:", removed)
