# -*- coding: utf-8 -*-
"""手写分镜入库工具: python mk_sb.py <ep> <json文件>"""
import json, os, sys
CACHE = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/09_缓存"
os.makedirs(CACHE, exist_ok=True)
ep = int(sys.argv[1])
sb = json.load(open(sys.argv[2], encoding="utf-8"))
sb["ep"] = ep
p = os.path.join(CACHE, "EP%03d.json" % ep)
json.dump(sb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", p, "shots=", len(sb["shots"]))
