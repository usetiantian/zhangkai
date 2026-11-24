# -*- coding: utf-8 -*-
"""重跑镜2：加强『青光劈落』，保留原定妆照场景"""
import json, sys, urllib.request
sys.path.insert(0, r"C:\Users\87999\claude-workspace")
from h3_driver import build_graph
from gen_wjcs_ep01 import GLOBAL, mk, SEED, REF

API="http://127.0.0.1:8188"
def post(p,d):
    r=urllib.request.Request(API+p,data=json.dumps(d).encode("utf-8"),
        headers={"Content-Type":"application/json"},method="POST")
    return json.loads(urllib.request.urlopen(r,timeout=60).read().decode())

P2=("镜 2｜中近景·仰角｜<Picture 1> 中的少年林问在昏暗的卧房中猛然仰起头，"
    "一道炽烈的青色光柱从头顶轰然劈落，穿过屋梁的缝隙直直砸进他的眉心，"
    "光柱周围炸开成无数旋转的青色光粒与气流旋涡，强烈青光把他的整张脸和灰蓝麻布短袍照亮，"
    "头发被气浪猛烈掀起。他瞳孔骤缩，嘴唇微张，震惊地大口喘息。"
    "镜头快速向他的面部推近。"
    "｜环境音：尖锐剑鸣骤然炸响、少年急促的呼吸、屋瓦震颤｜")

segs=[mk(0,P2,5.5,refs=[REF])]
g,proj=build_graph(json.dumps(segs,ensure_ascii=False),ui_mode="create",
                    global_prompt=GLOBAL,steps=8,project_id="wjcs_xueji_v2")
r=post("/prompt",{"prompt":g,"client_id":"seg2fix"})
print("project_id:",proj); print("prompt_id:",r["prompt_id"])
print("node_errors:",json.dumps(r.get("node_errors",{}),ensure_ascii=False)[:1500])
open(r"C:\Users\87999\claude-workspace\wjcs_prompt_id.txt","w").write(r["prompt_id"])
