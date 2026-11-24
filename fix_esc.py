# -*- coding: utf-8 -*-
"""修复 postproduce.py 里被吞掉一层反斜杠的转义"""
B = chr(92)
F = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/postproduce.py"
t = open(F, encoding="utf-8").read()
pairs = [
    ('.replace("{", "' + B + '{")',  '.replace("{", "' + B + B + '{")'),
    ('.replace("}", "' + B + '}")',  '.replace("}", "' + B + B + '}")'),
    ('.replace("' + chr(10) + '", "' + B + 'N")',
     '.replace("' + chr(10) + '", "' + B + B + 'N")'),
    ('.replace(":", "' + B + ':")',  '.replace(":", "' + B + B + ':")'),
]
n = 0
for bad, good in pairs:
    if bad in t:
        t = t.replace(bad, good); n += 1
open(F, "w", encoding="utf-8").write(t)
print("patched", n, "patterns")
