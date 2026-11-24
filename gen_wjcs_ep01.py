# -*- coding: utf-8 -*-
"""《问剑长生·血祭古剑》漫剧短片生成 —— 4 镜分镜 -> H3DirectorStudio"""
import json, sys, os
sys.path.insert(0, r"C:\Users\87999\claude-workspace")
from h3_driver import build_graph, run

SEED = 880211
REF = "wjcs_linwen.png"

GLOBAL = (
    "中国仙侠3D国漫动画风格（3D donghua animation），电影级渲染，赛璐璐卡通着色，"
    "硬边明暗交界，强烈轮廓边缘光，冷青与暖橙对比色调，体积雾与丁达尔光束。\n"
    "主角林问：16岁中国少年，身形清瘦单薄，眉清目秀神情执拗，黑发束成简单发髻，"
    "穿灰蓝色磨损麻布短袍，袖口毛边，腰束皮带。<Picture 1> 为林问的形象参考，"
    "保持相同的面部特征、发型与服装。\n"
    "无字幕，无水印，无画面文字。"
)

SHOTS = [
    ("镜 1｜大全景｜云海之巅·剑灵",
     "镜 1｜大全景｜云雾缭绕的仙山之巅，脚下是翻涌的云海，远处剑峰穿出云层。"
     "一道背对镜头的高大身影立于崖边，身形挺拔如剑，手中横握一柄残破古剑，"
     "剑身泛着淡青色光芒，剑气如丝缕般向上升腾并在云中散开，面容隐没在逆光中不可见。"
     "镜头自高空缓慢而平稳地向前推进，越过云海靠近那道身影。"
     "｜环境音：高空呼啸的风声、悠远低沉的剑鸣、衣袍猎猎｜"),

    ("镜 2｜中近景·仰角｜青光入体",
     "镜 2｜中近景｜仰角拍摄。<Picture 1> 中的少年林问仰面望天，瞳孔骤然收缩，"
     "一道炽烈的青色光柱从画面上方轰然砸下直冲他的眉心，光芒刺穿云雾炸开成无数光粒。"
     "他的头发与灰蓝麻布短袍被狂风猛烈掀起，面部被青光完全照亮。"
     "镜头快速向他的面部推近。"
     "｜环境音：尖锐剑鸣骤然炸响、少年急促的呼吸、狂风｜"),

    ("镜 3｜中景｜铁匠铺·残剑颤鸣",
     "镜 3｜中景｜昏暗破旧的铁匠铺内部，墙上挂着生锈的农具，角落堆着成堆废铁，"
     "油灯发出昏黄暖光，炉火余烬明灭。<Picture 1> 中的林问正弯腰抡锤打铁，"
     "突然动作停住，缓缓转头看向身后的废铁堆。废铁堆里一柄残破古剑静静躺着，"
     "剑身正轻微震颤，缝隙里透出忽明忽暗的青色微光。"
     "镜头从他的背后缓缓横移到侧面，把废铁堆里的古剑纳入画面。"
     "｜环境音：炉火噼啪、金属余震嗡鸣、远处风铃｜"),

    ("镜 4｜特写｜血祭·剑灵苏醒",
     "镜 4｜特写｜<Picture 1> 中林问粗糙的右手缓缓伸向古剑的剑柄，"
     "指尖即将触到缠绕剑柄的旧布条。就在指尖接触剑柄的一刹那，"
     "整柄残剑猛地爆发出刺目的青色光芒，光芒顺着剑身冲进他的手掌并沿着手臂向上蔓延，"
     "林问的瞳孔在青光中缩成一点。镜头快速推近至手与剑柄的极近特写。"
     "｜环境音：能量爆发的低频轰鸣、远古苍老的一声叹息｜"),
]

def mk(i, prompt, dur=5.5, refs=None):
    return {
        "prompt": prompt, "seed": SEED,
        "refs": refs if refs is not None else [REF],
        "video_refs": [], "video_ref_modes": {}, "video_audio_reference": False,
        "duration": dur, "inherit_shared": True, "use_tail": False,
        "first_frame_mode": "none", "first_frame": "", "last_frame": "",
        "enabled": True, "force": False,
        "manual_refs": [], "parsed_refs": [], "auto_refs": [], "audio_src": "model",
        "second_sample": {"mode": "off"}, "second_sample_auto": False,
        "continuity_mode": "off",
        "voice_refs": [], "voice_labels": {}, "parsed_asset_ids": [],
        "use_global_prompt": True, "prompt_asset_bindings": [],
        "prompt_picture_order": "segment", "sample_stage": "full",
    }

if __name__ == "__main__":
    segs = [mk(i, p) for i, (t, p) in enumerate(SHOTS)]
    segs_json = json.dumps(segs, ensure_ascii=False)
    g, pid = build_graph(segs_json, ui_mode="create", global_prompt=GLOBAL,
                         steps=8, project_id="wjcs_xueji_v1")
    print("project_id:", pid, "segments:", len(segs), "total_dur:", sum(s["duration"] for s in segs), flush=True)
    _, h = run(g, label="XUEJI", poll=10)
    if h:
        print("---- OUTPUTS ----")
        print(json.dumps(h.get("outputs", {}), ensure_ascii=False)[:4000])
