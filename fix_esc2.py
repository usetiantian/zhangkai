# -*- coding: utf-8 -*-
B = chr(92)
F = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/postproduce.py"
t = open(F, encoding="utf-8").read()
bad = '.replace("' + B + 'n", "' + B + 'N")'
good = '.replace("' + B + 'n", "' + B + B + 'N")'
print("found:", bad in t)
t = t.replace(bad, good)
open(F, "w", encoding="utf-8").write(t)
