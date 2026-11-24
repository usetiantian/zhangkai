# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
t = open(F, encoding="utf-8").read()

old = '''def build_h3_prompt(sh, pairs):
    """把 LLM 分镜转成 H3 提示词，并把参考图标记注入角色提及处。"""
    visual = sh["visual"]
    for i, (name, _) in enumerate(pairs, 1):
        if name in visual:
            visual = visual.replace(name, "<Picture %d> 中的%s" % (i, name), 1)
    return ("镜 %d｜%s｜%s %s｜环境音：%s｜"
            % (sh["idx"], sh["shot_size"], visual, sh["camera"], sh["ambience"]))'''

new = '''def build_h3_prompt(sh, pairs):
    """把 LLM 分镜转成 H3 提示词。

    关键：参考图在 H3 里是「软约束」，模型先验可能压过图片。
    因此把定妆照档案里的外貌描述一并写进正文，让「文字」和「图片」指向同一形象，
    两者叠加才稳定。
    """
    visual = sh["visual"]
    idx = ref_lib.load_index()
    for i, (name, _) in enumerate(pairs, 1):
        if name not in visual:
            continue
        app = ""
        meta = idx.get(name) or {}
        if meta.get("appearance"):
            app = "（%s）" % meta["appearance"]
        visual = visual.replace(name, "<Picture %d> 中的%s%s" % (i, name, app), 1)
    return ("镜 %d｜%s｜%s %s｜环境音：%s｜"
            % (sh["idx"], sh["shot_size"], visual, sh["camera"], sh["ambience"]))'''

assert old in t, "build_h3_prompt pattern missing"
t = t.replace(old, new)
open(F, "w", encoding="utf-8").write(t)
print("build_h3_prompt: 外貌描述已注入")
