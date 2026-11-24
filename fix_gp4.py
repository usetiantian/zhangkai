# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
lines = open(F, encoding="utf-8").read().split(chr(10))
i = 33
print("before:", repr(lines[i][-30:]))
if lines[i].rstrip().endswith('""'):
    lines[i] = lines[i].rstrip()[:-1]
open(F, "w", encoding="utf-8").write(chr(10).join(lines))
print("after:", repr(lines[i][-30:]))
