# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本")
import llm_storyboard as L
from produce_ep import read_chapter
ch, fn = read_chapter(3)
msgs = [{"role": "system", "content": L.SYSTEM},
        {"role": "user", "content": "第 3 章正文：\n\n" + ch}]
raw = L.call_llm(msgs)
print("RAW LEN:", len(raw))
print("RAW HEAD >>>")
print(raw[:1500])
print("<<< RAW TAIL")
print(raw[-800:])
print("CLEANED:")
c = L._clean_json(raw)
print(repr(c[:300]))
