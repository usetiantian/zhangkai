# -*- coding: utf-8 -*-
"""修复 postproduce.py / produce_ep.py（用占位符避免反斜杠被吞）"""
NL = chr(10)
BS = chr(92)
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"

# ---------- 1) postproduce.concat_and_burn ----------
F = D + "postproduce.py"
t = open(F, encoding="utf-8").read()
i = t.index("def concat_and_burn(")
tmpl = '''def concat_and_burn(shot_videos, master_wav, ass_path, out_path, crf=18):
    """视频流拼接 + 挂成品音轨 + 烧 ASS 字幕。

    Windows 下 ass filter 的路径转义很脆弱（冒号 + 中文目录名）。
    做法：把字幕复制到纯 ASCII 临时目录，用相对文件名引用，cwd 指向该目录。
    """
    import shutil
    tmpd = tempfile.mkdtemp(prefix="epburn_")
    lst = os.path.join(tmpd, "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for v in shot_videos:
            fh.write("file '%s'{BS}n" % v.replace("{BS}{BS}", "/"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    shutil.copy2(ass_path, os.path.join(tmpd, "subs.ass"))
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", lst,
           "-i", master_wav,
           "-map", "0:v:0", "-map", "1:a:0", "-vf", "ass=subs.ass",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, cwd=tmpd)
    return out_path
'''
new = tmpl.replace("{BS}", BS)
t = t[:i] + new
open(F, "w", encoding="utf-8").write(t)
print("postproduce.py fixed")

# ---------- 2) produce_ep 断点续跑 ----------
F2 = D + "produce_ep.py"
t2 = open(F2, encoding="utf-8").read()
helper = '''
def _shot_files(proj, n, suffix):
    """已产出的分段素材，全部齐才返回，否则 None。"""
    out = []
    for i in range(1, n + 1):
        g = sorted(glob.glob(os.path.join(H.H3_OUT, proj, "漫剧_seg%d_*%s*.mp4" % (i, suffix))))
        if not g:
            return None
        out.append(g[-1])
    return out


'''
anchor = "# ---------------- 主流程 ----------------"
if "_shot_files(" not in t2:
    t2 = t2.replace(anchor, helper + anchor)

old3 = '''    g, _ = H.build_graph(segs, global_prompt=GLOBAL_TMPL + ("{BS}n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                          ui_mode="create", steps=8, project_id=proj)
    H.run(g, label="EP%03d-一采" % ep_no)'''.replace("{BS}", BS)
new3 = '''    if _shot_files(proj, len(segs), "一次采样"):
        log("      已有一采，跳过（断点续跑）")
    else:
        g, _ = H.build_graph(segs, global_prompt=GLOBAL_TMPL + ("{BS}n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                              ui_mode="create", steps=8, project_id=proj)
        H.run(g, label="EP%03d-一采" % ep_no)'''.replace("{BS}", BS)
if old3 in t2:
    t2 = t2.replace(old3, new3)
else:
    print("  WARN: 一采段模式未匹配")

old4 = '''        segs2 = []
        for sh in sb["shots"]:
            p = pairs.get(sh["idx"], [])
            segs2.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                         duration=SHOT_DUR, refs=[f for _, f in p],
                                         second=H.DEFAULT_SECOND, first_pass_version=2))
        g2, _ = H.build_graph(segs2, global_prompt=GLOBAL_TMPL + ("{BS}n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                               ui_mode="create", steps=8, project_id=proj)
        H.run(g2, label="EP%03d-二采" % ep_no)'''.replace("{BS}", BS)
new4 = '''        if _shot_files(proj, len(sb["shots"]), "二次采样"):
            log("      已有二采，跳过（断点续跑）")
        else:
            segs2 = []
            for sh in sb["shots"]:
                p = pairs.get(sh["idx"], [])
                segs2.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                             duration=SHOT_DUR, refs=[f for _, f in p],
                                             second=H.DEFAULT_SECOND, first_pass_version=2))
            g2, _ = H.build_graph(segs2, global_prompt=GLOBAL_TMPL + ("{BS}n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                                   ui_mode="create", steps=8, project_id=proj)
            H.run(g2, label="EP%03d-二采" % ep_no)'''.replace("{BS}", BS)
if old4 in t2:
    t2 = t2.replace(old4, new4)
else:
    print("  WARN: 二采段模式未匹配")
open(F2, "w", encoding="utf-8").write(t2)
print("produce_ep.py fixed")
