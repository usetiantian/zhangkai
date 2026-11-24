# -*- coding: utf-8 -*-
"""生成镜2专用参考图：云海山巅·青光入体 -> ComfyUI/input/wjcs_linwen_m2.png"""
import json, time, urllib.request, os, sys
API = "http://127.0.0.1:8188"
INPUT = r"D:\ComfyUI_windows_portable\ComfyUI\input"
POS = ("Chinese xianxia donghua movie still, 3D animated film style, cel-shaded render, "
       "extreme low angle shot looking up at a 16-year-old Chinese boy swordsman, thin frail build, "
       "clean sharp eyebrows, stubborn determined eyes wide open in shock, black hair tied in a simple "
       "short topknot, wearing a worn grey-blue coarse hemp short robe with frayed sleeves and a "
       "leather belt, his hair and robe whipped violently upward by wind. He stands on a rocky peak "
       "above a vast rolling sea of clouds, sword peaks piercing the cloud layer in the distance. "
       "A blinding column of cyan light crashes straight down from the sky onto his forehead, "
       "exploding into countless glowing particles that pierce the clouds. Overhead backlight, "
       "volumetric god rays, cold cyan against deep blue, cinematic, high detail, sharp focus, "
       "3D donghua movie still")
NEG = ("interior, indoor, room, house, wooden wall, window, lamp, table, low quality, blurry, "
       "out of focus, jpeg artifacts, deformed hands, extra fingers, mutated hands, extra limbs, "
       "asymmetrical eyes, cross-eyed, watermark, text, signature, logo, subtitles, "
       "photorealistic skin pores, flat shading, sketch, lowpoly")
graph = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}},
    "11": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux", "device": "default"}},
    "12": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
    "16": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 576, "batch_size": 1}},
    "13": {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["11", 0]}},
    "14": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["11", 0]}},
    "20": {"class_type": "KSampler", "inputs": {"seed": 550377, "steps": 26, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            "model": ["1", 0], "positive": ["13", 0], "negative": ["14", 0], "latent_image": ["16", 0]}},
    "17": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["12", 0]}},
    "18": {"class_type": "SaveImage", "inputs": {"filename_prefix": "wjcs_ref2", "images": ["17", 0]}},
}
def post(p,d):
    r=urllib.request.Request(API+p,data=json.dumps(d).encode(),headers={"Content-Type":"application/json"},method="POST")
    return json.loads(urllib.request.urlopen(r,timeout=60).read().decode())
def get(p): return json.loads(urllib.request.urlopen(API+p,timeout=60).read().decode())
pid = post("/prompt", {"prompt": graph, "client_id":"ref2"})["prompt_id"]
print("prompt_id",pid,flush=True)
t0=time.time()
while time.time()-t0<900:
    time.sleep(5); h=get("/history/"+pid)
    if pid in h:
        hh=h[pid]
        if hh.get("status",{}).get("status_str")=="error":
            print("ERR",json.dumps(hh.get("status",{}),ensure_ascii=False)[:2500]); sys.exit(1)
        if hh.get("status",{}).get("completed"):
            fn=hh["outputs"]["18"]["images"][0]
            url="%s/view?filename=%s&subfolder=%s&type=%s"%(API,fn["filename"],fn["subfolder"],fn["type"])
            data=urllib.request.urlopen(url,timeout=60).read()
            dst=os.path.join(INPUT,"wjcs_linwen_m2.png")
            open(dst,"wb").write(data); print("copied ->",dst,len(data)); sys.exit(0)
    else: print("t=%ds"%int(time.time()-t0),flush=True)
print("TIMEOUT")
