# -*- coding: utf-8 -*-
# 纯本地代码改写：把 chapter_to_shots 换成带 assistant 预填充的版本
F = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/llm_storyboard.py"
t = open(F, encoding="utf-8").read()
i = t.index("def chapter_to_shots(")
j = t.index("VALID_SIZES =")
nl = chr(10)
new = (
'def _base_msgs(chapter_text, ep_no):' + nl +
'    """assistant 预填充：强制模型从 JSON 开头续写。"""' + nl +
'    return [{"role": "system", "content": SYSTEM},' + nl +
'            {"role": "user", "content": ("第 %d 章正文：" % ep_no) + ' + repr(nl + nl) + ' + chapter_text},' + nl +
'            {"role": "assistant", "content": "{"}]' + nl + nl + nl +
'def chapter_to_shots(chapter_text, ep_no, retries=3):' + nl +
'    last = None' + nl +
'    for attempt in range(retries):' + nl +
'        msgs = _base_msgs(chapter_text, ep_no)' + nl +
'        try:' + nl +
'            raw = call_llm(msgs)' + nl +
'            if not raw or not raw.strip():' + nl +
'                raise ValueError("empty")' + nl +
'            data = json.loads(_clean_json(raw))' + nl +
'            if not isinstance(data.get("shots"), list) or not data["shots"]:' + nl +
'                raise ValueError("shots empty")' + nl +
'            return normalize(data, ep_no)' + nl +
'        except Exception as e:' + nl +
'            last = e' + nl +
'            print("  [llm] attempt %d failed: %s" % (attempt + 1, e), flush=True)' + nl +
'            time.sleep(3)' + nl +
'    raise RuntimeError("storyboard failed: %s" % last)' + nl + nl + nl)
open(F, "w", encoding="utf-8").write(t[:i] + new + t[j:])
print("patched")
