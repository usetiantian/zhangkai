# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "llm_storyboard.py"
t = open(F, encoding="utf-8").read()
old = '''def call_llm(messages, timeout=600):
    body = {"messages": messages}'''
new = '''def call_llm(messages, timeout=900, max_tokens=8000):
    # 插件路由默认 max_tokens=1200，会被 MiniMax-M3 的思考过程吃光导致 JSON 被截断。
    # 插件内部上限为 8000。
    body = {"messages": messages, "max_tokens": max_tokens}'''
assert old in t
t = t.replace(old, new)

old2 = '''            raw = call_llm(msgs)'''
new2 = '''            raw = call_llm(msgs)
            if not raw or not raw.strip():
                raise ValueError("LLM 返回空内容（max_tokens 可能被思考过程耗尽）")'''
assert old2 in t
t = t.replace(old2, new2)
open(F, "w", encoding="utf-8").write(t)
print("llm_storyboard.py patched")
