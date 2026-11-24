# -*- coding: utf-8 -*-
"""H3DirectorStudio API driver: replicate H3Director_merged.json model chain, swap segments_json."""
import json, time, uuid, urllib.request

API = "http://127.0.0.1:8188"

def _post(path, payload):
    req = urllib.request.Request(
        API + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def _get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def build_graph(segments_json, tsegments_json="[]", vsegments_json="[]",
                ui_mode="create", global_prompt="", steps=8, duration=5.5,
                sampler="res_multistep", scheduler="simple", ref_image_size="match",
                project_id=None, lora_turbo=True, lora_mystic=True):
    pid = project_id or ("wjcs_" + uuid.uuid4().hex[:12])
    g = {
        "10": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors",
            "weight_dtype": "default"}},
        "186": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["10", 0],
            "lora_name": "minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors",
            "strength_model": 1.0}},
        "187": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["186", 0],
            "lora_name": "MysticXXX_MMH3-V1.safetensors",
            "strength_model": 0.5}},
        "11": {"class_type": "PathchSageAttentionKJ", "inputs": {
            "model": ["187", 0], "sage_attention": "auto", "allow_compile": False}},
        "39": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["11", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "4": {"class_type": "MiniMaxLowVRAMAttention", "inputs": {
            "model": ["39", 0], "head_chunks": 4}},
        "9": {"class_type": "MiniMaxChunkFeedForward", "inputs": {
            "model": ["4", 0], "chunks": 2, "seq_threshold": 4096}},
        "14": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_32b_minimax_h3_bf16.safetensors",
            "type": "minimax", "device": "default"}},
        "15": {"class_type": "VAELoader", "inputs": {
            "vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "16": {"class_type": "VAELoader", "inputs": {
            "vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "20": {"class_type": "ResolutionSelector", "inputs": {
            "aspect_ratio": "16:9 (Widescreen)", "megapixels": 0.4, "multiple": 32}},
        "13": {"class_type": "H3DirectorStudio", "inputs": {
            "model": ["9", 0], "clip": ["14", 0], "vae": ["15", 0], "audio_vae": ["16", 0],
            "width": ["20", 0], "height": ["20", 1],
            "时长秒": duration, "steps": steps, "sampler": sampler, "scheduler": scheduler,
            "ref_image_size": ref_image_size,
            "segments_json": segments_json,
            "vsegments_json": vsegments_json,
            "tsegments_json": tsegments_json,
            "ui_mode": ui_mode,
            "global_prompt": global_prompt,
            "续接方式": "软参考Ref2VA(保人物)",
            "每段后卸载模型": False,
            "汇总输出": "仅预览帧(推荐)",
            "project_id": pid,
            "text_shared_refs_json": "[]"}},
    }
    return g, pid

def run(graph, label="job", poll=8, timeout=100000):
    cid = _post("/prompt", {"prompt": graph, "client_id": "h3driver"})
    pid = cid["prompt_id"]
    print("[%s] queued prompt_id=%s" % (label, pid), flush=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            hist = _get("/history/" + pid)
        except Exception:
            continue
        if pid in hist:
            h = hist[pid]
            st = h.get("status", {})
            print("[%s] status=%s completed=%s" % (label, st.get("status_str"), st.get("completed")), flush=True)
            if st.get("status_str") == "error":
                print(json.dumps(h.get("status", {}), ensure_ascii=False, indent=1)[:4000], flush=True)
                return pid, h
            if st.get("completed"):
                return pid, h
        else:
            q = _get("/queue")
            running = q.get("queue_running", [])
            pend = q.get("queue_pending", [])
            if running:
                try:
                    ct = list(running[0][2].values())[0].get("class_type", "?")
                except Exception:
                    ct = "?"
                print("[%s] t=%4ds running %s" % (label, int(time.time() - t0), ct), flush=True)
            else:
                print("[%s] t=%4ds pending=%d" % (label, int(time.time() - t0), len(pend)), flush=True)
    print("[%s] TIMEOUT" % label, flush=True)
    return pid, None
