# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r"C:\Users\87999\claude-workspace")
from h3_driver import build_graph, run

SEED = 20261108
def seg(prompt, dur, **kw):
    s = {
        "prompt": prompt, "seed": SEED, "refs": [], "video_refs": [], "video_ref_modes": {},
        "video_audio_reference": False, "duration": dur, "inherit_shared": True, "use_tail": False,
        "first_frame_mode": "none", "first_frame": "", "last_frame": "", "enabled": True, "force": False,
        "manual_refs": [], "parsed_refs": [], "auto_refs": [], "audio_src": "model",
        "second_sample": {"mode": "off"}, "second_sample_auto": False,
        "continuity_mode": "off", "voice_refs": [], "voice_labels": {}, "parsed_asset_ids": [],
        "use_global_prompt": True, "prompt_asset_bindings": [], "prompt_picture_order": "segment",
        "sample_stage": "full",
    }
    s.update(kw)
    return s

prompt = ("镜 1｜大全景｜云雾缭绕的仙山之巅，云海翻涌，一道模糊的持剑身影立于崖边，"
          "手中古剑泛着淡青色光芒，剑气缓缓流转｜环境音：高空风声、低沉剑鸣｜3s")

segs = json.dumps([seg(prompt, 2.0)], ensure_ascii=False)
g, pid = build_graph(segs, ui_mode="create", project_id="wjcs_smoke_01")
print("project_id:", pid)
_, h = run(g, label="SMOKE", poll=6)
if h:
    print("---- OUTPUTS ----")
    print(json.dumps(h.get("outputs", {}), ensure_ascii=False)[:3000])
