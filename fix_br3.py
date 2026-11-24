# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "batch_run.py"
lines = open(F, encoding="utf-8").read().split(chr(10))
for i in range(70, 80):
    print(i, repr(lines[i]))
