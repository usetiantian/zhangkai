"""换装：以旧定妆图为底图做图生图，只改服装/发型/配饰，脸保持不变。

用法:
  python tools/manga_costume.py --base dingzhuang_林渺_00002.png \
      --out dingzhuang_林渺_00003.png --desc "改穿深青色内门道袍，束发玉冠"
"""
import io
import json
import os
import shutil
import sys
import time
import urllib.request

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
COMFY_ROOT = os.environ.get("COMFY_ROOT", "D:/ComfyUI_windows_portable/ComfyUI")
INPUT_DIR = os.path.join(COMFY_ROOT, "input")

STYLE = ("国产玄幻动漫风格角色设定图，高饱和度厚涂上色，精细锐利描边，深邃明暗对比与体积光，"
         "人物边缘有轮廓光，精致五官，七点五头身写实比例")
NEGATIVE = ("儿童，幼态，Q版，大头娃娃脸，幼童比例，平头，寸头，板寸，现代发型，短发齐耳，"
            "欧美发型，3D写实，真人照片，欧美卡通，日式少年漫，平涂赛璐璐，暖黄复古色调，"
            "颗粒感，复古滤镜，老电影质感，水墨晕染，模糊，畸变，多余手指，文字，水印，签名，"
            "换脸，不同的人，不同的五官")
UNET = "qwen_image_2.1_int8_convrot.safetensors"
CLIP = "qwen3vl_8b_int8_convrot.safetensors"
VAE = "qwen_image_2.1_vae_bf16.safetensors"


def _post(path, payload, timeout=3600):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(COMFY + path, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _get(path, timeout=60):
    with urllib.request.urlopen(COMFY + path, timeout=timeout) as resp:
        return json.load(resp)


def build_prompt(base, desc, out, seed=1, size=1328):
    prompt = ("%s。<image1>是同一位角色，保持其面部特征、脸型、眉眼、肤色完全不变，"
              "只更换服装与配饰：%s。严格保持 <image1> 的三视图排布、构图、纯灰背景、"
              "三个视图里完全相同的面部特征不变，只把身上的衣服、鞋袜、发饰换成新的。" % (STYLE, desc))
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": CLIP, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "QwenImage21Cache",
              "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": base}},
        "6": {"class_type": "ImageScaleToTotalPixels",
              "inputs": {"image": ["5", 0], "upscale_method": "lanczos",
                         "megapixels": 1.0, "resolution_steps": 1}},
        "7": {"class_type": "TextEncodeQwenImage21",
              "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": NEGATIVE,
                         "resolution": 0, "images.image_1": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "EmptyLatentImage",
              "inputs": {"width": size, "height": size, "batch_size": 1}},
        "9": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "positive": ["7", 0], "negative": ["7", 1],
                         "latent_image": ["8", 0], "seed": seed, "steps": 25, "cfg": 1.0,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 0.55}},
        "10": {"class_type": "VAEDecode",
               "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImageAdvanced",
               "inputs": {"images": ["10", 0], "filename_prefix": "manga/" + os.path.splitext(os.path.basename(out))[0],
                          "format": "png", "format.bit_depth": "8-bit",
                          "format.input_color_space": "sRGB"}},
    }


def main():
    args = sys.argv[1:]
    base = out = desc = None
    for i, a in enumerate(args):
        if a == "--base":
            base = args[i + 1]
        elif a == "--out":
            out = args[i + 1]
        elif a == "--desc":
            desc = args[i + 1]
    if not (base and out and desc):
        print(__doc__)
        return 1
    src = os.path.join(INPUT_DIR, base)
    if not os.path.exists(src):
        print("底图不在 input 目录:", src)
        return 1
    res = _post("/prompt", {"prompt": build_prompt(base, desc, out, seed=int(time.time()) % 100000)})
    pid = res["prompt_id"]
    print("已提交换装, prompt_id =", pid, flush=True)
    while True:
        hist = _get("/history/" + pid)
        if pid in hist:
            st = hist[pid].get("status") or {}
            if st.get("status_str") != "success":
                print("失败:", st.get("status_str"))
                for m in (st.get("messages") or [])[-4:]:
                    print("  ", str(m)[:300])
                return 1
            for oid, val in (hist[pid].get("outputs") or {}).items():
                for img in (val.get("images") or []):
                    s = os.path.join(COMFY_ROOT, "output", img.get("subfolder") or "", img.get("filename"))
                    d = os.path.join(INPUT_DIR, out)
                    shutil.copyfile(s, d)
                    print("新造型 ->", d)
                    print("记得把 %s 写进 00_素材/当前造型.json" % out)
            return 0
        time.sleep(10)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
