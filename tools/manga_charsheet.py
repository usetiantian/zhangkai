"""用本地 Qwen-Image 生成角色定妆三视图（纯文生图）。

用途：把角色的脸和服装锁成一张参考图，之后作为导演台分段里的 refs 传给 H3，
人物跨镜头就不会飘。没有参考图时 H3 只能靠文字描述，角色长相必然不稳定。

用法:
  python tools/manga_charsheet.py                 # 生成全部角色
  python tools/manga_charsheet.py --only 林渺
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
NEGATIVE = ("儿童，幼态，Q版，大头娃娃脸，幼童比例，平头，寸头，板寸，现代发型，短发齐耳，欧美发型，络腮胡，华丽铠甲，"
            "现代服装，白衬衫，西装，汽车，玻璃幕墙，3D写实，真人照片，欧美卡通，日式少年漫，"
            "平涂赛璐璐，暖黄复古色调，颗粒感，复古滤镜，老电影质感，水墨晕染，模糊，畸变，"
            "多余手指，文字，水印，签名")

CHARS = {
    "林渺": ("十六岁少年男性，仙侠少年侠客造型：黑色长发在头顶束成高马尾，用深青色布发带扎紧，"
             "其余黑发披散到肩背，鬓边留几缕碎发；面容清瘦俊朗，轮廓分明，肩背挺拔宽展，"
             "颈线清晰可见喉结，是成年少年面容不是孩童；身形抽长偏瘦，小麦色皮肤，脸型清瘦偏长，"
             "颧骨略高，细长眼，眼神沉稳内敛不爱笑；身穿灰蓝色交领束袖劲装，窄袖收口露腕，"
             "深褐色束腰，外罩灰蓝色短褂，下摆开衩便于行动，深灰绑腿，黑色布靴；"
             "腰间挂一个拇指大小的青色小葫芦，葫芦温润青玉质地有细微荧光",
             "三视图设定稿：正面全身、侧面全身、背面全身并排，同一个人同一张脸，纯灰色背景"),
    "苏禾": ("十七岁少女女性，身量已长成少女身段，个子高挑，鹅蛋脸，白净皮肤，细长眉眼眼尾微挑；"
             "黑色长发在头顶盘成圆髻，一支银色发簪固定，不披发不垂肩；白色交领罗裙，青色披帛搭在臂弯，"
             "素面绣花鞋，腰间一块羊脂玉佩；神情清冷疏离",
             "三视图设定稿：正面全身、侧面全身、背面全身并排，同一个人同一张脸，纯灰色背景"),
    "王天霸": ("十七岁青年男性，身形壮实，肩膀宽厚，比普通少年高出半个头，一脸横肉；"
               "短黑发用黑色发冠束起；穿暗纹锦缎长袍，腰佩玉饰；神情趾高气扬",
               "三视图设定稿：正面全身、侧面全身、背面全身并排，同一个人同一张脸，纯灰色背景"),
    "林守田": ("四十余岁中年男性，头发花白大半用灰色布巾束在脑后，额头和眼角有明显皱纹，"
               "身形清瘦、背有些佝偻；穿灰布短衫，手掌粗糙，神态老实疲惫",
               "三视图设定稿：正面全身、侧面全身、背面全身并排，同一个人同一张脸，纯灰色背景"),
    "林小雨": ("十二岁小姑娘，稚嫩圆脸，双丫髻扎着红头绳，穿红碎花布衫，个头只到哥哥肩膀",
               "三视图设定稿：正面全身、侧面全身、背面全身并排，同一个人同一张脸，纯灰色背景"),
}

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


def build_prompt(name, seed=1, size=1328):
    look, extra = CHARS[name]
    prompt = "%s。%s。%s。纯灰色背景，无文字，无水印，无边框。" % (STYLE, look, extra)
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": CLIP, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "QwenImage21Cache",
              "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "5": {"class_type": "TextEncodeQwenImage21",
              "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": NEGATIVE,
                         "resolution": 0, "vae": ["3", 0]}},
        "6": {"class_type": "EmptyLatentImage",
              "inputs": {"width": size, "height": size, "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["5", 1],
                         "latent_image": ["6", 0], "seed": seed, "steps": 25, "cfg": 1.0,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImageAdvanced",
              "inputs": {"images": ["8", 0], "filename_prefix": "manga/dingzhuang_" + name,
                         "format": "png", "format.bit_depth": "8-bit",
                         "format.input_color_space": "sRGB"}},
    }


def main():
    args = sys.argv[1:]
    names = list(CHARS.keys())
    if "--only" in args:
        names = [n for n in args[args.index("--only") + 1:] if n in CHARS]
    for idx, name in enumerate(names):
        print("[%d/%d] 生成 %s 定妆 ..." % (idx + 1, len(names), name), flush=True)
        res = _post("/prompt", {"prompt": build_prompt(name, seed=20261117 + idx)})
        pid = res["prompt_id"]
        while True:
            hist = _get("/history/" + pid)
            if pid in hist:
                st = hist[pid].get("status") or {}
                if st.get("status_str") != "success":
                    print("  失败:", st.get("status_str"))
                    for m in (st.get("messages") or [])[-4:]:
                        print("   ", str(m)[:300])
                    break
                for oid, val in (hist[pid].get("outputs") or {}).items():
                    for img in (val.get("images") or []):
                        src = os.path.join(COMFY_ROOT, "output", img.get("subfolder") or "",
                                           img.get("filename"))
                        dst = os.path.join(INPUT_DIR, img.get("filename"))
                        shutil.copyfile(src, dst)
                        print("  ->", dst, flush=True)
                break
            time.sleep(10)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
