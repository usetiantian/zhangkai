# -*- coding: utf-8 -*-
"""生成「视频换脸 (ReActor)」ComfyUI 工作流 —— 全原生节点路径"""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

WF_DIR = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
OUT = os.path.join(WF_DIR, '视频换脸_ReActor.json')

nodes = []
links = []
_lid = [0]

def add_link(oid, oslot, tid, tslot, ty):
    _lid[0] += 1
    lid = _lid[0]
    links.append([lid, oid, oslot, tid, tslot, ty])
    return lid

def set_in(node, name, link):
    for i in node.get('inputs', []):
        if i['name'] == name:
            i['link'] = link
            return
    raise KeyError(node['type'] + ' missing input ' + name)

def set_out(node, idx, lk):
    node['outputs'][idx]['links'] = lk

def W(*pairs):
    """widgets_values list + named dict"""
    vals = [v for _, v in pairs]
    named = {k: v for k, v in pairs}
    return vals, named

def mk(nid, typ, pos, size, order, title, inputs, outputs, wvals, wnamed, props=None):
    n = {
        "id": nid, "type": typ, "pos": pos, "size": size,
        "flags": {}, "order": order, "mode": 0,
        "inputs": inputs, "outputs": outputs,
        "properties": props or {"Node name for S&R": typ},
        "widgets_values": wvals,
    }
    if wnamed:
        n["widgets_values_named"] = wnamed
    n["title"] = title
    nodes.append(n)
    return n

def sock(name, ty, link=None, widget=False):
    d = {"name": name, "type": ty, "link": link}
    if widget:
        d["widget"] = {"name": name}
    return d

def out(name, ty, links=None):
    return {"name": name, "type": ty, "links": links}

# ===== 1. LoadVideo (原生) =====
wv, wn = W(("file", "抖音202695-416805.mp4"))
wv.append("image")
n1 = mk(1, "LoadVideo", [60, 300], [420, 640], 0, "1. 载入源视频",
        [sock("file", "COMBO")],
        [out("VIDEO", "VIDEO")],
        wv, wn, {"Node name for S&R": "LoadVideo", "cnr_id": "comfy-core", "ver": "0.24.0"})

# ===== 2. LoadImage 定妆脸 =====
wv, wn = W(("image", "wjcs_linwen.png"))
wv.append("image")
n2 = mk(2, "LoadImage", [60, 40], [420, 460], 1, "2. 定妆脸 (角色参考图)",
        [],
        [out("IMAGE", "IMAGE"), out("MASK", "MASK")],
        wv, wn, {"Node name for S&R": "LoadImage", "cnr_id": "comfy-core", "ver": "0.24.0"})

# ===== 3. ReActorBuildFaceModel =====
wv, wn = W(("save_mode", True), ("send_only", False),
           ("face_model_name", "manju_role_01"), ("compute_method", "Mean"))
n3 = mk(3, "ReActorBuildFaceModel", [560, 40], [340, 150], 2, "3. 锁定角色脸 (多图融合)",
        [sock("images", "IMAGE")],
        [out("FACE_MODEL", "FACE_MODEL")],
        wv, wn)

# ===== 4. ReActorFaceSwap =====
wv, wn = W(("enabled", True), ("swap_model", "inswapper_128_fp16.onnx"),
           ("facedetection", "retinaface_resnet50"), ("face_restore_model", "GFPGANv1.4.pth"),
           ("face_restore_visibility", 1), ("codeformer_weight", 0.5),
           ("detect_gender_input", "no"), ("detect_gender_source", "no"),
           ("input_faces_index", "0"), ("source_faces_index", "0"),
           ("console_log_level", 1))
n4 = mk(4, "ReActorFaceSwap", [960, 300], [340, 380], 4, "4. 换脸 (逐帧)",
        [sock("input_image", "IMAGE"), sock("source_image", "IMAGE"), sock("face_model", "FACE_MODEL")],
        [out("SWAPPED_IMAGE", "IMAGE"), out("FACE_MODEL", "FACE_MODEL"), out("ORIGINAL_IMAGE", "IMAGE")],
        wv, wn)

# ===== 5. GetVideoComponents =====
n5 = mk(5, "GetVideoComponents", [60, 1000], [260, 170], 3, "5. 拆出画面/音轨/帧率",
        [sock("video", "VIDEO")],
        [out("images", "IMAGE"), out("audio", "AUDIO"), out("fps", "FLOAT"), out("bit_depth", "INT")],
        [], {})

# ===== 6. CreateVideo =====
wv, wn = W(("fps", 24), ("bit_depth", "auto"), ("color_space", "sRGB"),
           ("chroma_subsampling", "auto"), ("codec", "none"))
n6 = mk(6, "CreateVideo", [1360, 300], [320, 200], 5, "6. 合成视频",
        [sock("images", "IMAGE"), sock("fps", "FLOAT", widget=True), sock("audio", "AUDIO"),
         sock("bit_depth", "COMBO", widget=True), sock("color_space", "COMBO", widget=True),
         sock("chroma_subsampling", "COMBO", widget=True), sock("codec", "COMBO", widget=True)],
        [out("VIDEO", "VIDEO")],
        wv, wn, {"Node name for S&R": "CreateVideo", "cnr_id": "comfy-core", "ver": "0.22.0"})

# ===== 7. SaveVideo =====
wv, wn = W(("filename_prefix", "video/faceswap"), ("format", "auto"), ("codec", "auto"))
wv.append("auto")
n7 = mk(7, "SaveVideo", [1740, 300], [420, 320], 6, "7. 保存视频",
        [sock("video", "VIDEO")],
        [out("video", "VIDEO")],
        wv, wn, {"Node name for S&R": "SaveVideo", "cnr_id": "comfy-core", "ver": "0.22.0"})

# ===== 8. GetImageRangeFromBatch =====
wv, wn = W(("start_index", 0), ("num_frames", 1))
n8 = mk(8, "GetImageRangeFromBatch", [1360, 880], [320, 140], 7, "8. 取第1帧 (检查用)",
        [sock("images", "IMAGE"), sock("masks", "MASK"),
         sock("start_index", "INT", widget=True), sock("num_frames", "INT", widget=True)],
        [out("IMAGE", "IMAGE"), out("MASK", "MASK")],
        wv, wn, {"Node name for S&R": "GetImageRangeFromBatch", "cnr_id": "comfyui-kjnodes"})

# ===== 9. PreviewImage =====
n9 = mk(9, "PreviewImage", [1740, 880], [340, 300], 8, "9. 预览换脸结果",
        [sock("images", "IMAGE")], [], [], {})

# ===== 10. ReActorFaceSimilarity =====
n10 = mk(10, "ReActorFaceSimilarity", [1360, 1080], [340, 140], 9,
         "10. 相似度打分 (定妆脸 vs 换脸结果)",
         [sock("image1", "IMAGE"), sock("image2", "IMAGE")],
         [out("similarity_float", "FLOAT"), out("similarity_text", "STRING")], [], {})

# ===== 11. ShowText =====
n11 = mk(11, "ShowText|pysssss", [1760, 1080], [340, 140], 10, "11. 相似度结果",
         [sock("text", "STRING")], [], [], {},
         {"Node name for S&R": "ShowText|pysssss"})

# ===== 12. AUSBOSS_NODES_WorkflowNote =====
# 用后端真实注册的注释节点（MarkdownNote 只有前端静态定义，
# 会让 ComfyUI 的「缺失节点包」提示多出一条）
BODY = (
    "1. 节点2「定妆脸」载入角色参考图（正面、清晰、无遮挡）\n"
    "2. 节点3「锁定角色脸」把脸锁成可复用模型；多张参考图可再接一个 ReActorBuildFaceModel 融合\n"
    "3. 节点1 选源视频\n"
    "4. 节点4 执行换脸（逐帧处理，长片不吃显存）\n"
    "5. 节点5 自动取原片帧率和音轨 → 节点6 合成 → 节点7 保存\n"
    "6. 节点10/11 给出与定妆脸的相似度分数，可用来卡质量\n\n"
    "---\n\n"
    "注意：\n"
    "· 侧脸 / 低头 / 手挡脸容易穿帮，先用短片验证\n"
    "· 源视频音轨会原样带到输出\n"
    "· 显存紧张用 inswapper_128_fp16.onnx\n"
    "· face_restore 强度 1.0，过高会有塑料感\n"
    "· 长视频建议分段跑，避免一次占满内存"
)
note_obj = {
    "v": 1,
    "title": "视频换脸 (ReActor)",
    "subtitle": "把源视频里的脸换成你的角色定妆脸 · 逐帧处理",
    "author": "CC",
    "layout": "card",
    "accent": "",
    "body": BODY,
    "models": [
        {"name": "inswapper_128_fp16.onnx", "dir": "insightface", "size": "264 MB",
         "url": "https://hf-mirror.com/datasets/Gourieff/ReActor/resolve/main/models/inswapper_128_fp16.onnx"},
        {"name": "buffalo_l", "dir": "insightface/models/buffalo_l", "size": "275 MB",
         "url": "https://hf-mirror.com/datasets/Gourieff/ReActor/resolve/main/models/buffalo_l.zip"},
        {"name": "GFPGANv1.4.pth", "dir": "facerestore_models", "size": "333 MB",
         "url": "https://hf-mirror.com/datasets/Gourieff/ReActor/resolve/main/models/facerestore_models/GFPGANv1.4.pth"},
        {"name": "face_yolov8m.pt", "dir": "ultralytics/bbox", "size": "50 MB",
         "url": "https://hf-mirror.com/datasets/Gourieff/ReActor/resolve/main/models/detection/bbox/face_yolov8m.pt"},
    ],
}
n12 = mk(12, "AUSBOSS_NODES_WorkflowNote", [60, 1240], [440, 723], 11, "使用说明",
         [sock("note", "STRING", widget=True)], [],
         [json.dumps(note_obj, ensure_ascii=False)], {},
         {"cnr_id": "ausboss-nodes", "ver": "2.2.0",
          "Node name for S&R": "AUSBOSS_NODES_WorkflowNote"})

# ---------- 连线 ----------
L1  = add_link(1, 0, 5, 0, 'VIDEO')        # 源视频 -> 拆组件
L2  = add_link(2, 0, 3, 0, 'IMAGE')        # 定妆脸 -> 锁脸
L3  = add_link(3, 0, 4, 2, 'FACE_MODEL')   # 锁脸 -> 换脸
L4  = add_link(5, 0, 4, 0, 'IMAGE')        # 视频帧 -> 换脸
L5  = add_link(4, 0, 6, 0, 'IMAGE')        # 换脸结果 -> 合成
L6  = add_link(5, 2, 6, 1, 'FLOAT')        # fps -> 合成
L7  = add_link(5, 1, 6, 2, 'AUDIO')        # 音轨 -> 合成
L8  = add_link(6, 0, 7, 0, 'VIDEO')        # 合成 -> 保存
L9  = add_link(4, 0, 8, 0, 'IMAGE')        # 换脸结果 -> 取帧
L10 = add_link(8, 0, 9, 0, 'IMAGE')        # -> 预览
L11 = add_link(2, 0, 10, 0, 'IMAGE')       # 定妆脸 -> 相似度
L12 = add_link(8, 0, 10, 1, 'IMAGE')       # 换脸帧 -> 相似度
L13 = add_link(10, 1, 11, 0, 'STRING')     # 相似度文本 -> 显示

set_out(n1, 0, [L1])
set_out(n2, 0, [L2, L11])
set_in(n3, 'images', L2); set_out(n3, 0, [L3])
set_in(n4, 'input_image', L4); set_in(n4, 'face_model', L3); set_out(n4, 0, [L5, L9])
set_in(n5, 'video', L1); set_out(n5, 0, [L4]); set_out(n5, 1, [L7]); set_out(n5, 2, [L6])
set_in(n6, 'images', L5); set_in(n6, 'fps', L6); set_in(n6, 'audio', L7); set_out(n6, 0, [L8])
set_in(n7, 'video', L8)
set_in(n8, 'images', L9); set_out(n8, 0, [L10, L12])
set_in(n9, 'images', L10)
set_in(n10, 'image1', L11); set_in(n10, 'image2', L12); set_out(n10, 1, [L13])
set_in(n11, 'text', L13)

wf = {
    "id": "uuid-vfs-0001",
    "revision": 0,
    "last_node_id": 12,
    "last_link_id": len(links),
    "nodes": nodes,
    "links": links,
    "groups": [],
    "definitions": {"subgraphs": []},
    "config": {},
    "extra": {},
    "version": 0.4,
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)
print('OK ->', OUT)
print('nodes', len(nodes), 'links', len(links))
