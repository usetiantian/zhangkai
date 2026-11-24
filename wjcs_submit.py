# -*- coding: utf-8 -*-
"""提交《问剑长生·血祭古剑》漫剧任务到本机 ComfyUI (H3DirectorStudio)，只提交不阻塞。"""
import json, sys, urllib.request
sys.path.insert(0, r"C:\Users\87999\claude-workspace")
from h3_driver import build_graph
from gen_wjcs_ep01 import SHOTS, GLOBAL, mk, SEED, REF

API = "http://127.0.0.1:8188"

def post(p, d):
    r = urllib.request.Request(API+p, data=json.dumps(d).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode("utf-8"))

segs = [mk(i, p) for i, (t, p) in enumerate(SHOTS)]
g, proj = build_graph(json.dumps(segs, ensure_ascii=False), ui_mode="create",
                     global_prompt=GLOBAL, steps=8, project_id="wjcs_xueji_v1")
r = post("/prompt", {"prompt": g, "client_id": "wjcs"})
print("project_id:", proj)
print("prompt_id:", r["prompt_id"])
print("node_errors:", json.dumps(r.get("node_errors", {}), ensure_ascii=False)[:2000])
open(r"C:\Users\87999\claude-workspace\wjcs_prompt_id.txt","w").write(r["prompt_id"])
