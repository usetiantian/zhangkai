# -*- coding: utf-8 -*-
"""
H3DirectorStudio API 驱动核心
=============================
复刻 ComfyUI-H3-Director 的 H3DirectorStudio 节点模型链，可通过 HTTP API 直接提交。

节点链（与 H3Director_merged.json 一致）:
  UNETLoader(minimax_h3_hybrid_fl2va_ref2va_b25-49-int8)
    -> LoraLoaderModelOnly(minimax_h3_turbo_v4_step600)
    -> LoraLoaderModelOnly(MysticXXX_MMH3-V1)
    -> PathchSageAttentionKJ(auto)
    -> MiniMaxH3SigmaShift(shift_video=12, shift_audio=3)
    -> MiniMaxLowVRAMAttention(head_chunks=4)
    -> MiniMaxChunkFeedForward(chunks=2, seq_threshold=4096)
    -> H3DirectorStudio(segments_json / ui_mode=create)
"""
import json, time, uuid, urllib.request

API = "http://127.0.0.1:8188"
COMFY = "D:/ComfyUI_windows_portable/ComfyUI"
H3_OUT = COMFY + "/output/video/h3director"


def _post(path, payload):
    req = urllib.request.Request(
        API + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def _get(path):
    return json.loads(urllib.request.urlopen(API + path, timeout=60).read().decode("utf-8"))


def build_graph(segments_json, global_prompt="", ui_mode="create", steps=8,
                duration=5.5, sampler="res_multistep", scheduler="simple",
                ref_image_size="match", project_id=None, second_sample=None):
    """构造 API graph。segments_json: list[dict] 或已序列化的 str。"""
    if not isinstance(segments_json, str):
        segments_json = json.dumps(segments_json, ensure_ascii=False)
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
            "model": ["186", 0], "lora_name": "MysticXXX_MMH3-V1.safetensors",
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
            "vsegments_json": "[]", "tsegments_json": "[]",
            "ui_mode": ui_mode, "global_prompt": global_prompt,
            "续接方式": "软参考Ref2VA(保人物)",
            "每段后卸载模型": False, "汇总输出": "仅预览帧(推荐)",
            "project_id": pid, "text_shared_refs_json": "[]"}},
    }
    return g, pid


def submit(graph, client_id="h3driver"):
    r = _post("/prompt", {"prompt": graph, "client_id": client_id})
    if r.get("node_errors"):
        raise RuntimeError("节点校验失败: " + json.dumps(r["node_errors"], ensure_ascii=False)[:1500])
    return r["prompt_id"]


def wait(prompt_id, label="job", poll=10, timeout=200000):
    """轮询直到完成；返回 history dict。"""
    t0 = time.time()
    print("[%s] prompt_id=%s" % (label, prompt_id), flush=True)
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            hist = _get("/history/" + prompt_id)
        except Exception:
            continue
        if prompt_id in hist:
            h = hist[prompt_id]
            st = h.get("status", {})
            print("[%s] %s completed=%s (%.0fs)" % (label, st.get("status_str"),
                  st.get("completed"), time.time() - t0), flush=True)
            if st.get("status_str") == "error":
                print(json.dumps(st, ensure_ascii=False)[:3000], flush=True)
            return h
        q = _get("/queue")
        print("[%s] t=%4ds running=%d pending=%d" % (label, int(time.time() - t0),
              len(q.get("queue_running", [])), len(q.get("queue_pending", []))), flush=True)
    raise TimeoutError(label)


def run(graph, label="job", **kw):
    return wait(submit(graph), label=label, **kw)


# ---------- 分段构造 ----------
DEFAULT_SECOND = {
    "mode": "custom", "strategy": "latent_repair", "preset_version": 4,
    "high_steps": 2, "steps": 2,
    "upscaler_model": "minimax_h3_latent_upscaler_3d_fp16.safetensors",
    "target_size_mode": "megapixels", "target_megapixels": 1.0,
}


def make_segment(prompt, seed, duration=5.5, refs=None, enabled=True,
                 continuity="off", continuity_src=0, second=None, first_pass_version=None):
    """构造 H3DirectorStudio 的一个 segment。"""
    seg = {
        "prompt": prompt, "seed": seed,
        "refs": list(refs or []),
        "video_refs": [], "video_ref_modes": {}, "video_audio_reference": False,
        "duration": duration, "inherit_shared": True, "use_tail": False,
        "first_frame_mode": "none", "first_frame": "", "last_frame": "",
        "enabled": enabled, "force": False,
        "manual_refs": [], "parsed_refs": [], "auto_refs": [], "audio_src": "model",
        "second_sample": dict(second) if second else {"mode": "off"},
        "second_sample_auto": bool(second),
        "continuity_mode": continuity,
        "voice_refs": [], "voice_labels": {}, "parsed_asset_ids": [],
        "use_global_prompt": True, "prompt_asset_bindings": [],
        "prompt_picture_order": "segment", "sample_stage": "full",
    }
    if continuity_src:
        seg["continuity_source_segment"] = continuity_src
    if first_pass_version is not None:
        seg["sample_stage"] = "second"
        seg["first_pass_version"] = first_pass_version
    return seg
