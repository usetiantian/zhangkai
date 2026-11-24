#!/usr/bin/env python3
"""doctor.py -- environment checks for the music3 desktop app.

Answers the three questions a new user actually has:
  1. is ComfyUI running and reachable?
  2. are the three MiniMax Music3 model files present (and how big)?
  3. is there a GPU?
"""
import json, os, shutil, socket, subprocess, sys, urllib.request

MODEL_FILES = [
    ("unet", "minimax_music3_dit_fp16.safetensors",
     "diffusion_models", 4_914_197_682),
    ("unet_lowvram", "minimax_music3_dit_int8_convrot.safetensors",
     "diffusion_models", 2_502_161_682),
    ("clip", "minimax_music3_text_encoder_pruned_int8_convrot.safetensors",
     "text_encoders", 9_196_611_886),
    ("vae", "minimax_music3_dav.safetensors", "vae", 216_696_128),
]

MODEL_REPO = "https://hf-mirror.com/Comfy-Org/MiniMax-Music3"
MODEL_REPO_ALT = "https://huggingface.co/Comfy-Org/MiniMax-Music3"

# Where a ComfyUI install usually lives on Windows.
COMFY_CANDIDATES = [
    r"D:\ComfyUI_windows_portable", r"C:\ComfyUI_windows_portable",
    r"C:\ComfyUI", r"D:\ComfyUI",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\ComfyUI"),
]


def comfy_alive(url="http://127.0.0.1:8188", timeout=4):
    try:
        req = urllib.request.Request(url.rstrip("/") + "/system_stats")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def find_comfy_install():
    """Return a plausible ComfyUI root dir, or None."""
    for p in COMFY_CANDIDATES:
        if p and os.path.isdir(p):
            inner = os.path.join(p, "ComfyUI")
            if os.path.isdir(inner):
                return p
            if os.path.isdir(os.path.join(p, "models")):
                return p
    # one level of scan under the user's home / D:\
    for base in (os.path.expanduser("~"), "D:\\", "C:\\"):
        if not os.path.isdir(base):
            continue
        try:
            for name in os.listdir(base):
                if "comfy" in name.lower():
                    full = os.path.join(base, name)
                    if os.path.isdir(os.path.join(full, "ComfyUI", "models")) or \
                       os.path.isdir(os.path.join(full, "models")):
                        return full
        except Exception:
            continue
    return None


def models_dir(comfy_root):
    if not comfy_root:
        return None
    for cand in (os.path.join(comfy_root, "ComfyUI", "models"),
                 os.path.join(comfy_root, "models")):
        if os.path.isdir(cand):
            return cand
    return None


def check_models(root):
    """root = models directory. Returns list of per-file status."""
    out = []
    for key, fname, subdir, expected in MODEL_FILES:
        item = {"key": key, "file": fname, "subdir": subdir,
                "expected": expected, "present": False, "size": 0, "path": None}
        if root:
            p = os.path.join(root, subdir, fname)
            if os.path.isfile(p):
                item["present"] = True
                item["size"] = os.path.getsize(p)
                item["path"] = p
        out.append(item)
    return out


def check_gpu():
    exe = shutil.which("nvidia-smi")
    if not exe:
        for p in (r"C:\Windows\System32\nvidia-smi.exe",
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
            if os.path.isfile(p):
                exe = p
                break
    if not exe:
        return {"ok": False, "name": None, "vram_mb": None, "reason": "nvidia-smi 不在 PATH"}
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8)
        line = (out.stdout or "").strip().splitlines()[0]
        name, mem = [x.strip() for x in line.split(",")]
        return {"ok": True, "name": name, "vram_mb": int(float(mem)), "reason": None}
    except Exception as e:
        return {"ok": False, "name": None, "vram_mb": None, "reason": str(e)[:120]}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def report(comfy_url="http://127.0.0.1:8188", comfy_root=None, do_gpu=True):
    root = comfy_root or find_comfy_install()
    md = models_dir(root)
    rep = {
        "comfy_url": comfy_url,
        "comfy_alive": comfy_alive(comfy_url),
        "comfy_root": root,
        "models_dir": md,
        "models": check_models(md),
        "model_repo": MODEL_REPO,
        "model_repo_alt": MODEL_REPO_ALT,
        "platform": sys.platform,
    }
    if do_gpu:
        rep["gpu"] = check_gpu()
    rep["ready"] = bool(rep["comfy_alive"] and md and
                        all(m["present"] for m in rep["models"] if m["key"] != "unet_lowvram"))
    return rep


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8188"
    root = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(report(url, root), ensure_ascii=False, indent=2))
