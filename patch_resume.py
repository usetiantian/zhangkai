# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
t = open(F, encoding="utf-8").read()

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
assert anchor in t
t = t.replace(anchor, helper + anchor)

# 一采前先看是否已有成品
old = '''    log("[EP%03d] 3/6 H3 一采 (%d 镜)..." % (ep_no, len(segs)))
    g, _ = H.build_graph(segs, global_prompt=GLOBAL_TMPL + ("\n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                          ui_mode="create", steps=8, project_id=proj)
    H.run(g, label="EP%03d-一采" % ep_no)'''
new = '''    log("[EP%03d] 3/6 H3 一采 (%d 镜)..." % (ep_no, len(segs)))
    if _shot_files(proj, len(segs), "一次采样"):
        log("      已有一采，跳过（断点续跑）")
    else:
        g, _ = H.build_graph(segs, global_prompt=GLOBAL_TMPL + ("\n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                              ui_mode="create", steps=8, project_id=proj)
        H.run(g, label="EP%03d-一采" % ep_no)'''
assert old in t, "pattern3 missing"
t = t.replace(old, new)

old2 = '''    if quality == "hd":
        log("[EP%03d] 4/6 H3 二采 (3D latent 放大 -> 1344x736)..." % ep_no)
        segs2 = []
        for sh in sb["shots"]:
            p = pairs.get(sh["idx"], [])
            segs2.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                         duration=SHOT_DUR, refs=[f for _, f in p],
                                         second=H.DEFAULT_SECOND, first_pass_version=2))
        g2, _ = H.build_graph(segs2, global_prompt=GLOBAL_TMPL + ("\n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                               ui_mode="create", steps=8, project_id=proj)
        H.run(g2, label="EP%03d-二采" % ep_no)
        suffix = "二次采样"'''
new2 = '''    if quality == "hd":
        log("[EP%03d] 4/6 H3 二采 (3D latent 放大 -> 1344x736)..." % ep_no)
        if _shot_files(proj, len(sb["shots"]), "二次采样"):
            log("      已有二采，跳过（断点续跑）")
        else:
            segs2 = []
            for sh in sb["shots"]:
                p = pairs.get(sh["idx"], [])
                segs2.append(H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],
                                             duration=SHOT_DUR, refs=[f for _, f in p],
                                             second=H.DEFAULT_SECOND, first_pass_version=2))
            g2, _ = H.build_graph(segs2, global_prompt=GLOBAL_TMPL + ("\n" + sb["global_prompt"] if sb.get("global_prompt") else ""),
                                   ui_mode="create", steps=8, project_id=proj)
            H.run(g2, label="EP%03d-二采" % ep_no)
        suffix = "二次采样"'''
assert old2 in t, "pattern4 missing"
t = t.replace(old2, new2)
open(F, "w", encoding="utf-8").write(t)
print("produce_ep.py: 断点续跑已加")
