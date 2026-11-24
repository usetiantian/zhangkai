# -*- coding: utf-8 -*-
import re
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
t = open(F, encoding="utf-8").read()

# 1) tts_engine 没有 re 模块 -> 用本地净化
old = 'wav = os.path.join(voicedir, "%02d_%s.wav" % (n, TTS.re.sub(r"[^\w]", "", d.get("role", "旁白")) or "na"))'
new = ('safe = "".join(ch for ch in d.get("role", "") if ch.isalnum()) or "na"\n'
       '            wav = os.path.join(voicedir, "%02d_%s.wav" % (n, safe))')
assert old in t, "pattern1 not found"
t = t.replace(old, new)

# 2) 复用已有的林问定妆照，不重新生成
old2 = '''    ref_lib.ensure_ref(MAIN_ROLE, "16岁中国少年，清瘦单薄，眉清目秀神情执拗，黑发束成简单发髻，"
                                  "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带", "少年铁匠之子")'''
new2 = '''    _idx = ref_lib.load_index()
    if MAIN_ROLE not in _idx:
        _legacy = os.path.join(ref_lib.INPUT, "wjcs_linwen.png")
        if os.path.isfile(_legacy):
            _idx[MAIN_ROLE] = {"file": "wjcs_linwen.png",
                               "appearance": "16岁中国少年，清瘦单薄，眉清目秀神情执拗",
                               "role": "少年铁匠之子"}
            ref_lib.save_index(_idx)
    if MAIN_ROLE not in ref_lib.load_index():
        ref_lib.ensure_ref(MAIN_ROLE, "16岁中国少年，清瘦单薄，眉清目秀神情执拗，黑发束成简单发髻，"
                                      "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带", "少年铁匠之子")'''
assert old2 in t, "pattern2 not found"
t = t.replace(old2, new2)

open(F, "w", encoding="utf-8").write(t)
print("produce_ep.py patched")
