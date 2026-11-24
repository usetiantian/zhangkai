# -*- coding: utf-8 -*-
"""用 flux1-dev fp8 生成林问定妆参考图 -> ComfyUI/input/wjcs_linwen.png"""
import json, time, urllib.request, os, sys
API = "http://127.0.0.1:8188"
INPUT = r"D:\ComfyUI_windows_portable\ComfyUI\input"

POS = ("Chinese xianxia donghua movie still, 3D animated film style, cel-shaded render with hard "
       "terminator, Unreal Engine quality render. Character design sheet portrait of a 16-year-old "
       "Chinese boy swordsman, thin frail build, clean sharp eyebrows, stubborn determined eyes, "
       "black hair tied in a simple short topknot, wearing a worn grey-blue coarse hemp short robe "
       "with frayed sleeves and a leather belt. He holds a broken ancient longsword with a chipped "
       "blade and faint cyan glow along the fuller. Standing in a humble dim blacksmith workshop, "
       "warm oil lamp light from the left, cold cyan rim light from behind, dust motes floating, "
       "strong backlight, cinematic, high detail, sharp focus, 3D donghua movie still")

NEG = ("low quality, blurry, out of focus, jpeg artifacts, compression, deformed hands, extra fingers, "
       "six fingers, mutated hands, extra limbs, asymmetrical eyes, cross-eyed, disfigured, "
       "watermark, text, signature, logo, subtitles, modern clothing, jeans, t-shirt, western, "
       "photorealistic skin pores, flat shading, sketch, lowpoly")

graph = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}},
    "11": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux", "device": "default"}},
    "12": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
    "16": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 576, "batch_size": 1}},
    "13": {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["11", 0]}},
    "14": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["11", 0]}},
    "20": {"class_type": "KSampler", "inputs": {"seed": 880211, "steps": 24, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            "model": ["1", 0], "positive": ["13", 0], "negative": ["14", 0], "latent_image": ["16", 0]}},
    "17": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["12", 0]}},
    "18": {"class_type": "SaveImage", "inputs": {"filename_prefix": "wjcs_ref", "images": ["17", 0]}},
}

def post(p, d):
    r = urllib.request.Request(API+p, data=json.dumps(d).encode(), headers={"Content-Type":"application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode())

def get(p):
    return json.loads(urllib.request.urlopen(API+p, timeout=60).read().decode())

pid = post("/prompt", {"prompt": graph, "client_id": "refgen"})["prompt_id"]
print("prompt_id", pid, flush=True)
t0=time.time()
while time.time()-t0 < 900:
    time.sleep(5)
    h = get("/history/"+pid)
    if pid in h:
        hh=h[pid]
        if hh.get("status",{}).get("status_str")=="error":
            print("ERROR", json.dumps(hh.get("status",{}),ensure_ascii=False)[:3000]); sys.exit(1)
        if hh.get("status",{}).get("completed"):
            outs = hh["outputs"]
            fn = outs["18"]["images"][0]
            print("saved:", fn, flush=True)
            url = "%s/view?filename=%s&subfolder=%s&type=%s" % (API, fn["filename"], fn["subfolder"], fn["type"])
            data = urllib.request.urlopen(url, timeout=60).read()
            dst = os.path.join(INPUT, "wjcs_linwen.png")
            open(dst,"wb").write(data)
            print("copied ->", dst, len(data), flush=True)
            sys.exit(0)
    else:
        print("t=%ds" % int(time.time()-t0), flush=True)
print("TIMEOUT")
