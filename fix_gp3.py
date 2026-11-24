# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
lines = open(F, encoding="utf-8").read().split(chr(10))
i = 33
assert lines[i].rstrip().endswith('",'), repr(lines[i])
lines[i] = lines[i].rstrip()[:-1] + '"'
open(F, "w", encoding="utf-8").write(chr(10).join(lines))
print("removed trailing comma (GLOBAL_TMPL was a tuple)")
