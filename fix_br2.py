# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "batch_run.py"
lines = open(F, encoding="utf-8").read().split(chr(10))
# 删掉 74-76 行(误插入到 --list 分支里的块)，保留 88-90 的正确位置
del lines[73:76]
open(F, "w", encoding="utf-8").write(chr(10).join(lines))
print("removed stray block")
