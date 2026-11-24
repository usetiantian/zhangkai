# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本")
import produce_ep as pe, ref_lib
sb = json.load(open("D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/09_缓存/EP002.json", encoding="utf-8"))
pairs = pe.shot_ref_pairs(sb)
print("index:", json.dumps(ref_lib.load_index(), ensure_ascii=False))
for sh in sb["shots"]:
    print("--- 镜%d  refs=%s" % (sh["idx"], pairs.get(sh["idx"])))
    print("    prompt:", pe.build_h3_prompt(sh, pairs.get(sh["idx"], []))[:220])
