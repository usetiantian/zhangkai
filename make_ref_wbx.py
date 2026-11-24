# -*- coding: utf-8 -*-
"""生成王半仙(书铺老秀才)参考图 -> ComfyUI/input/wjcs_wangbanxian.png"""
import json, time, urllib.request, os, sys
API="http://127.0.0.1:8188"; INPUT="D:/ComfyUI_windows_portable/ComfyUI/input"
POS=("Chinese xianxia donghua movie still, 3D animated film style, cel-shaded render, "
     "medium shot of an elderly Chinese scholar in his sixties, owner of a small town bookshop, "
     "thin weathered face with deep wrinkles, sparse wispy grey beard, long grey hair tied in a "
     "loose topknot, wearing a faded dark blue-grey scholar's robe with frayed edges. "
     "He holds a heavily rusted ancient bronze-corrupted longsword with both hands and examines it "
     "closely, his casual eyes suddenly snapping into sharp intense shock, eyebrows raised, "
     "mouth slightly open, expression complex and grave. Dim old bookshop interior, wooden shelves "
     "stacked with yellowed thread-bound books and bamboo scroll rolls, warm oil-lamp light from the "
     "left, dust motes floating, strong cinematic rim light, high detail, sharp focus, "
     "3D donghua movie still")
NEG=("young, child, boy, youthful, modern, t-shirt, jeans, elf, elf ears, pointed ears, chibi, "
     "cute cartoon, oversized head, low quality, blurry, out of focus, jpeg artifacts, "
     "deformed hands, extra fingers, mutated hands, extra limbs, asymmetrical eyes, cross-eyed, "
     "watermark, text, signature, logo, subtitles, flat shading, sketch, lowpoly")
g={
 "1":{"class_type":"UNETLoader","inputs":{"unet_name":"flux1-dev-fp8.safetensors","weight_dtype":"default"}},
 "11":{"class_type":"DualCLIPLoader","inputs":{"clip_name1":"t5xxl_fp8_e4m3fn.safetensors",
      "clip_name2":"clip_l.safetensors","type":"flux","device":"default"}},
 "12":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
 "16":{"class_type":"EmptyLatentImage","inputs":{"width":1024,"height":576,"batch_size":1}},
 "13":{"class_type":"CLIPTextEncode","inputs":{"text":POS,"clip":["11",0]}},
 "14":{"class_type":"CLIPTextEncode","inputs":{"text":NEG,"clip":["11",0]}},
 "20":{"class_type":"KSampler","inputs":{"seed":913377,"steps":26,"cfg":1.0,
      "sampler_name":"euler","scheduler":"simple","denoise":1.0,
      "model":["1",0],"positive":["13",0],"negative":["14",0],"latent_image":["16",0]}},
 "17":{"class_type":"VAEDecode","inputs":{"samples":["20",0],"vae":["12",0]}},
 "18":{"class_type":"SaveImage","inputs":{"filename_prefix":"wjcs_wangbanxian","images":["17",0]}},
}
def post(p,d):
    r=urllib.request.Request(API+p,data=json.dumps(d).encode(),headers={"Content-Type":"application/json"},method="POST")
    return json.loads(urllib.request.urlopen(r,timeout=60).read().decode())
def get(p): return json.loads(urllib.request.urlopen(API+p,timeout=60).read().decode())
pid=post("/prompt",{"prompt":g,"client_id":"wbx"})["prompt_id"]; print("pid",pid,flush=True)
t0=time.time()
while time.time()-t0<900:
    time.sleep(4); h=get("/history/"+pid)
    if pid in h:
        hh=h[pid]
        if hh.get("status",{}).get("status_str")=="error":
            print("ERR",json.dumps(hh.get("status",{}),ensure_ascii=False)[:2500]); sys.exit(1)
        if hh.get("status",{}).get("completed"):
            fn=hh["outputs"]["18"]["images"][0]
            url="%s/view?filename=%s&subfolder=%s&type=%s"%(API,fn["filename"],fn["subfolder"],fn["type"])
            data=urllib.request.urlopen(url,timeout=60).read()
            dst=os.path.join(INPUT,"wjcs_wangbanxian.png"); open(dst,"wb").write(data)
            print("copied ->",dst,len(data)); sys.exit(0)
    else: print("t=%ds"%int(time.time()-t0),flush=True)
print("TIMEOUT")
