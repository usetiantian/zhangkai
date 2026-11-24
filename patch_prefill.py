# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "llm_storyboard.py"
t = open(F, encoding="utf-8").read()
old = '''def chapter_to_shots(chapter_text, ep_no, retries=3):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "第 %d 章正文：\n\n%s" % (ep_no, chapter_text)}]
    last = None
    for attempt in range(retries):
        try:
            raw = call_llm(msgs)
            if not raw or not raw.strip():
                raise ValueError("LLM 返回空内容（max_tokens 可能被思考过程耗尽）")
            data = json.loads(_clean_json(raw))
            if not isinstance(data.get("shots"), list) or not data["shots"]:
                raise ValueError("shots 为空")
            return normalize(data, ep_no)
        except Exception as e:      # JSON 坏了 / 字段缺失 -> 重试
            last = e
            print("  [llm] 第%d次失败: %s" % (attempt + 1, e), flush=True)
            msgs.append({"role": "assistant", "content": raw if 'raw' in dir() else ""})
            msgs.append({"role": "user", "content":
                         "上次输出不是合法 JSON。请只输出一个 JSON 对象，不要代码块，不要思考过程。"})
            time.sleep(3)
    raise RuntimeError("LLM 分镜失败: %s" % last)'''
new = '''def _base_msgs(chapter_text, ep_no):
    """assistant 预填充 '{'：MiniMax-M3 会把 8000 token 全花在 <think> 上，
    预填充强制它从 JSON 开头续写，实测可稳定拿到完整 JSON。"""
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "第 %d 章正文：\n\n%s" % (ep_no, chapter_text)},
            {"role": "assistant", "content": "{"}]


def chapter_to_shots(chapter_text, ep_no, retries=3):
    last = None
    for attempt in range(retries):
        msgs = _base_msgs(chapter_text, ep_no)
        try:
            raw = call_llm(msgs)
            if not raw or not raw.strip():
                raise ValueError("LLM 返回空内容")
            data = json.loads(_clean_json(raw))
            if not isinstance(data.get("shots"), list) or not data["shots"]:
                raise ValueError("shots 为空")
            return normalize(data, ep_no)
        except Exception as e:
            last = e
            print("  [llm] 第%d次失败: %s" % (attempt + 1, e), flush=True)
            time.sleep(3)
    raise RuntimeError("LLM 分镜失败: %s" % last)'''
assert old in t, "pattern missing"
open(F, "w", encoding="utf-8").write(t.replace(old, new))
print("llm_storyboard.py: prefill enabled")
