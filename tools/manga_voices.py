"""给漫剧主要角色克隆/设计固定音色，并把样本放进 ComfyUI input 目录。

流程：
  1. 每个角色用 Qwen3-TTS 的 VoiceDesign（文字描述 -> 音色）生成一段干净台词音频
  2. 存到 ComfyUI 的 input 目录，文件名即角色名（如 林渺.wav）
  3. 之后在导演台的分段里写：
       "voice_refs":  ["林渺.wav"],
       "voice_modes": {"林渺.wav": "voice"}
     voice 模式 = 只学音色，台词仍由提示词给（copy 模式才是对口型配音）

用法：
  python tools/manga_voices.py            # 生成全部角色音色
  python tools/manga_voices.py --only 林渺 苏禾
"""
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
COMFY_ROOT = os.environ.get("COMFY_ROOT", "D:/ComfyUI_windows_portable/ComfyUI")
INPUT_DIR = os.path.join(COMFY_ROOT, "input")

# 角色 -> (音色描述, 样本台词)
VOICES = {
    "林渺": ("十六岁少年男声，偏低沉内敛，略带一点沙哑，语速偏慢，克制不张扬，带少年人特有的戒备感",
             "这雨，下得真不是时候。今日怕是走不成了。"),
    "苏禾": ("十七岁少女声线，清亮偏冷，吐字清晰利落，语速平稳，疏离克制中带一点好奇",
             "五灵根也不是一无是处。"),
    "王天霸": ("十七岁青年男声，浑厚张扬，粗粝带笑腔，跋扈外放，咬字重",
               "穿成这样就来了？灵根测试大会，不是乞丐收容所。"),
    "林守田": ("四十余岁中年男声，苍老沙哑，温和疲惫，语速慢，字与字之间留白多",
               "渺儿，王家下了帖子，明日去县城测灵根。"),
    "林小雨": ("十二岁小女孩声线，清脆微颤，带着藏不住的担心和害怕",
               "哥，你别去。王天霸每次见你都欺负你。"),
    "青葫道人": ("极老年男声，苍老低沉，带空旷回响，仙风道骨，气场压人，一字一顿",
                 "小娃娃，十三年来，老夫一直在等你的灵根觉醒。"),
}

SAMPLE_TEXT = "这雨，下得真不是时候。今日怕是走不成了。"


def _post(path, payload, timeout=1800):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(COMFY + path, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _get(path, timeout=60):
    with urllib.request.urlopen(COMFY + path, timeout=timeout) as resp:
        return json.load(resp)


def build_prompt(names):
    """一个 prompt 里放 N 组 VoiceDesign + SaveAudioMP3，模型只加载一次。"""
    prompt = {}
    for i, name in enumerate(names):
        instruct, text = VOICES[name]
        did = str(100 + i)
        prompt[did] = {
            "class_type": "FB_Qwen3TTSVoiceDesign",
            "inputs": {
                "text": text,
                "instruct": instruct,
                "model_choice": "1.7B",
                "device": "auto",
                "precision": "bf16",
                "language": "Chinese",
                "seed": 1000 + i,
                "attention": "sdpa",
                "x_vector_only": False,
                "unload_model_after": False,
            },
        }
        prompt[str(200 + i)] = {
            "class_type": "SaveAudioMP3",
            "inputs": {
                "filename_prefix": "voice/" + name,
                "quality": "320k",
                "audio": [did, 0],
            },
        }
    return prompt


def main():
    args = sys.argv[1:]
    names = list(VOICES.keys())
    if "--only" in args:
        i = args.index("--only")
        names = args[i + 1:]
        names = [n for n in names if n in VOICES]
    if not names:
        print("没有要生成的角色")
        return 1
    print("要生成的角色:", "、".join(names))
    prompt = build_prompt(names)
    res = _post("/prompt", {"prompt": prompt})
    pid = res["prompt_id"]
    print("已提交音色生成, prompt_id =", pid)
    while True:
        hist = _get("/history/" + pid)
        if pid in hist:
            status = hist[pid].get("status") or {}
            print("状态:", status.get("status_str"))
            if status.get("status_str") != "success":
                for m in (status.get("messages") or [])[-6:]:
                    print("  ", str(m)[:300])
                return 1
            outs = hist[pid].get("outputs") or {}
            out_dir = os.path.join(COMFY_ROOT, "output")
            copied = []
            for oid, val in outs.items():
                for aud in (val.get("audio") or []):
                    src = os.path.join(out_dir, aud.get("subfolder") or "",
                                       aud.get("filename"))
                    if not os.path.exists(src):
                        continue
                    base = os.path.splitext(aud.get("filename"))[0]
                    role = base.split("_")[0]
                    dst = os.path.join(INPUT_DIR, role + ".mp3")
                    shutil.copyfile(src, dst)
                    copied.append(dst)
                    print("音色样本 ->", dst)
            if not copied:
                print("没拿到音频输出，输出结构:", json.dumps(outs, ensure_ascii=False)[:400])
                return 1
            print("\n在导演台分段里这样绑定：")
            print(json.dumps({
                "voice_refs": [names[0] + ".mp3"],
                "voice_modes": {names[0] + ".mp3": "voice"},
            }, ensure_ascii=False))
            return 0
        time.sleep(10)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
