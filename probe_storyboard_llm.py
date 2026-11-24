# -*- coding: utf-8 -*-
"""
probe_storyboard_llm.py
只访问本机 ComfyUI (127.0.0.1:8188) 的导演台路由 /h3director/ai_prompt。
本脚本不读取、不存储、不传输任何 API 凭据 —— 凭据由 ComfyUI-H3-Director 插件内部持有。
"""
import json, urllib.request
URL = "http://127.0.0.1:8188/h3director/ai_prompt"
body = {"messages": [
    {"role": "system", "content": "你是分镜师。只输出严格 JSON，不要代码块。"},
    {"role": "user", "content": "把这句话拆成2个镜头的分镜 JSON，字段 shots[{shot_size,visual,camera}]: "
     "「少年在雨中的屋檐下抬头看天。」"}]}
req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
try:
    r = json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
    print("keys:", list(r.keys()))
    for k, v in r.items():
        print("  %s = %s" % (k, str(v)[:600]))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:800])
except Exception as e:
    print("ERR", type(e).__name__, e)
