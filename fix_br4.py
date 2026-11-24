# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "batch_run.py"
lines = open(F, encoding="utf-8").read().split(chr(10))
assert "only = [int(x)" in lines[73], repr(lines[73])
lines[73] = "    if a.list:"
lines[74] = "        m = load_manifest()"
open(F, "w", encoding="utf-8").write(chr(10).join(lines))
print("reconstructed --list branch")
for i in range(71, 78):
    print(i, repr(lines[i]))
