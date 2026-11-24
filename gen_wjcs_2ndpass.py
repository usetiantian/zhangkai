# -*- coding: utf-8 -*-
"""二采：对已有一采做 3D latent 放大 + 高清采样（864x480 -> ~1344x736）"""
import json, sys, urllib.request
sys.path.insert(0, r"C:\Users\87999\claude-workspace")
from h3_driver import build_graph
from gen_wjcs_ep01 import GLOBAL, SHOTS, mk, SEED, REF

API="http://127.0.0.1:8188"
def post(p,d):
    r=urllib.request.Request(API+p,data=json.dumps(d).encode("utf-8"),
        headers={"Content-Type":"application/json"},method="POST")
    return json.loads(urllib.request.urlopen(r,timeout=60).read().decode())

SECOND={"mode":"custom","strategy":"latent_repair","preset_version":4,"high_steps":2,"steps":2,
        "upscaler_model":"minimax_h3_latent_upscaler_3d_fp16.safetensors",
        "target_size_mode":"megapixels","target_megapixels":1.0}

def second_stage(proj, shot_indices, prompts):
    segs=[]
    for i in range(1,5):
        if i in shot_indices:
            s=mk(i-1, prompts[i-1], 5.5, refs=[REF])
            s["sample_stage"]="second"; s["first_pass_version"]=2
            s["second_sample"]=dict(SECOND); s["second_sample_auto"]=True
        else:
            s=mk(i-1,"",5.5,refs=[]); s["enabled"]=False
        segs.append(s)
    g,p=build_graph(json.dumps(segs,ensure_ascii=False),ui_mode="create",
                    global_prompt=GLOBAL,steps=8,project_id=proj)
    r=post("/prompt",{"prompt":g,"client_id":"second"})
    print("proj=%s prompt_id=%s errors=%s"%(proj,r["prompt_id"],json.dumps(r.get("node_errors",{}),ensure_ascii=False)[:600]))
    return r["prompt_id"]

if __name__=="__main__":
    a=second_stage("wjcs_xueji_v1",{1,3,4},[p for _,p in SHOTS])
    b=second_stage("wjcs_xueji_v2",{1},[SHOTS[1][1]])
    open(r"C:\Users\87999\claude-workspace\wjcs_2nd_ids.txt","w").write(a+"\n"+b)
    print("A=",a); print("B=",b)
