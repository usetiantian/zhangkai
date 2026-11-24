# -*- coding: utf-8 -*-
"""生成「视频换脸 (ReActor)」ComfyUI 工作流"""
import json, sys, copy, os
sys.stdout.reconfigure(encoding='utf-8')

WF_DIR = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
SRC_LONG = os.path.join(WF_DIR, '长视频 人物替换 .json')
SRC_SCAIL = os.path.join(WF_DIR, 'SCAIL-2 Int8 - Character Replacement.json')
OUT = os.path.join(WF_DIR, '视频换脸_ReActor.json')

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

SRC_DIR = WF_DIR

def node_of(wf, typ):
    for n in wf['nodes']:
        if n.get('type') == typ:
            return copy.deepcopy(n)
    raise KeyError(typ)

def node_of_any(typ, prefer=None):
    """在 workflows 目录所有工作流里找该类型节点，prefer 优先。"""
    order = []
    if prefer:
        order.append(prefer)
    for fn in sorted(os.listdir(SRC_DIR)):
        if fn.endswith('.json') and not fn.startswith('_'):
            p = os.path.join(SRC_DIR, fn)
            if p not in order:
                order.append(p)
    for p in order:
        try:
            wf = load(p)
        except Exception:
            continue
        for n in wf.get('nodes', []):
            if n.get('type') == typ:
                print('  template %-28s <- %s' % (typ, os.path.basename(p)))
                return copy.deepcopy(n)
    raise KeyError(typ)

long_wf = load(SRC_LONG)
scail_wf = load(SRC_SCAIL)

t_loadvideo = node_of_any('VHS_LoadVideo', prefer=SRC_LONG)
t_combine = node_of_any('VHS_VideoCombine', prefer=SRC_LONG)
t_range = node_of_any('GetImageRangeFromBatch', prefer=SRC_LONG)
t_loadimage = node_of_any('LoadImage', prefer=SRC_SCAIL)
t_preview = node_of_any('PreviewImage')
t_videocomp = node_of_any('GetVideoComponents', prefer=SRC_SCAIL)

nodes = []
links = []
_lid = [0]

def add_link(origin_id, origin_slot, target_id, target_slot, ltype):
    _lid[0] += 1
    lid = _lid[0]
    links.append([lid, origin_id, origin_slot, target_id, target_slot, ltype])
    return lid

def set_in(node, name, link):
    for i in node.get('inputs', []):
        if i['name'] == name:
            i['link'] = link
            return i
    raise KeyError(node['type'] + ' no input ' + name)

def set_out(node, idx, lk):
    node['outputs'][idx]['links'] = lk

def put(node, nid, pos, order, title):
    node['id'] = nid
    node['pos'] = pos
    node['order'] = order
    node['mode'] = 0
    node['title'] = title
    return node

# ===== 1. VHS_LoadVideo =====
n1 = put(t_loadvideo, 1, [60, 320], 0, '1. 载入源视频')
n1['widgets_values'] = {
    "video": "抖音202695-416805.mp4",
    "force_rate": 0,
    "custom_width": 0,
    "custom_height": 0,
    "frame_load_cap": 300,
    "skip_first_frames": 0,
    "select_every_nth": 1,
    "format": "None",
    "choose video to upload": "image",
    "videopreview": {"paused": False, "params": {"filename": "抖音202695-416805.mp4", "type": "input", "format": "video/h264-mp4"}},
}
nodes.append(n1)

# ===== 2. LoadImage 定妆脸 =====
n2 = put(t_loadimage, 2, [60, 60], 1, '2. 定妆脸 (角色参考图)')
n2['widgets_values'] = ["角色定妆脸.png", "image"]
nodes.append(n2)

# ===== 3. ReActorBuildFaceModel =====
n3 = {
    "id": 3, "type": "ReActorBuildFaceModel",
    "pos": [520, 60], "size": {"0": 315, "1": 130},
    "flags": {}, "order": 2, "mode": 0,
    "inputs": [{"name": "images", "type": "IMAGE", "link": None, "slot_index": 0}],
    "outputs": [{"name": "FACE_MODEL", "type": "FACE_MODEL", "links": None, "shape": 3, "slot_index": 0}],
    "properties": {"Node name for S&R": "ReActorBuildFaceModel"},
    "widgets_values": [True, False, "manju_role_01", "Mean"],
    "title": "3. 锁定角色脸 (多图融合)",
}
nodes.append(n3)

# ===== 4. ReActorFaceSwap =====
n4 = {
    "id": 4, "type": "ReActorFaceSwap",
    "pos": [900, 320], "size": {"0": 315, "1": 338},
    "flags": {}, "order": 4, "mode": 0,
    "inputs": [
        {"name": "input_image", "type": "IMAGE", "link": None, "slot_index": 0},
        {"name": "source_image", "type": "IMAGE", "link": None},
        {"name": "face_model", "type": "FACE_MODEL", "link": None},
    ],
    "outputs": [
        {"name": "SWAPPED_IMAGE", "type": "IMAGE", "links": None, "shape": 3, "slot_index": 0},
        {"name": "FACE_MODEL", "type": "FACE_MODEL", "links": None, "shape": 3},
        {"name": "ORIGINAL_IMAGE", "type": "IMAGE", "links": None, "shape": 3},
    ],
    "properties": {"Node name for S&R": "ReActorFaceSwap"},
    "widgets_values": [True, "inswapper_128_fp16.onnx", "retinaface_resnet50",
                       "GFPGANv1.4.pth", 1, 0.5, "no", "no", "0", "0", 1],
    "title": "4. 换脸 (逐帧)",
}
nodes.append(n4)

# ===== 5. GetVideoComponents =====
n5 = put(t_videocomp, 5, [60, 1080], 3, '5. 取源视频 fps / 音轨')
nodes.append(n5)

# ===== 6. VHS_VideoCombine =====
n6 = put(t_combine, 6, [1320, 320], 5, '6. 输出视频')
w = copy.deepcopy(t_combine.get('widgets_values') or {})
if not isinstance(w, dict):
    w = {}
w.update({"frame_rate": 24, "loop_count": 0, "filename_prefix": "video_faceswap",
           "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 19,
           "save_metadata": True, "trim_to_audio": False, "pingpong": False, "save_output": True})
n6['widgets_values'] = w
nodes.append(n6)

# ===== 7. GetImageRangeFromBatch =====
n7 = put(t_range, 7, [1320, 900], 6, '7. 取第1帧 (检查用)')
n7['widgets_values'] = [0, 1]
nodes.append(n7)

# ===== 8. PreviewImage =====
n8 = put(t_preview, 8, [1620, 900], 7, '8. 预览换脸结果')
nodes.append(n8)

# ===== 9. ReActorFaceSimilarity =====
n9 = {
    "id": 9, "type": "ReActorFaceSimilarity",
    "pos": [1320, 1180], "size": {"0": 300, "1": 120},
    "flags": {}, "order": 8, "mode": 0,
    "inputs": [
        {"name": "image1", "type": "IMAGE", "link": None, "slot_index": 0},
        {"name": "image2", "type": "IMAGE", "link": None, "slot_index": 1},
    ],
    "outputs": [
        {"name": "similarity_float", "type": "FLOAT", "links": None, "shape": 3, "slot_index": 0},
        {"name": "similarity_text", "type": "STRING", "links": None, "shape": 3, "slot_index": 1},
    ],
    "properties": {"Node name for S&R": "ReActorFaceSimilarity"},
    "widgets_values": [],
    "title": "9. 相似度打分 (定妆脸 vs 换脸结果)",
}
nodes.append(n9)

# ===== 10. ShowText =====
n10 = {
    "id": 10, "type": "ShowText|pysssss",
    "pos": [1660, 1180], "size": {"0": 300, "1": 120},
    "flags": {}, "order": 9, "mode": 0,
    "inputs": [{"name": "text", "type": "STRING", "link": None, "slot_index": 0}],
    "outputs": [],
    "properties": {"Node name for S&R": "ShowText|pysssss"},
    "widgets_values": [],
    "title": "10. 相似度结果",
}
nodes.append(n10)

# ===== 11. MarkdownNote =====
TICK = chr(96) * 3
note = (
    TICK + "\n# 视频换脸 (ReActor)\n\n"
    "1. 节点2 载入角色定妆脸（正面、清晰、无遮挡）\n"
    "2. 节点3 锁定角色脸 —— 多张参考图可再接一个 ReActorBuildFaceModel 融合\n"
    "3. 节点1 选源视频；force_rate 填 0 = 用原片帧率\n"
    "4. 节点4 执行换脸（逐帧处理，长片不吃显存）\n"
    "5. 节点9/10 给出与定妆脸的相似度分数，可用来卡质量\n\n"
    "## 注意\n"
    "- 侧脸/低头/遮挡容易穿帮，建议先小批量（frame_load_cap 300）验证\n"
    "- 源视频音轨会原样带到输出\n"
    "- 显存紧张可换 inswapper_128_fp16.onnx\n"
    "- face_restore_model 修脸强度 1.0，过高会有塑料感\n"
    + TICK + "\n"
)
n11 = {
    "id": 11, "type": "MarkdownNote",
    "pos": [60, 1360], "size": {"0": 700, "1": 420},
    "flags": {}, "order": 10, "mode": 0,
    "inputs": [], "outputs": [],
    "properties": {},
    "widgets_values": [note],
    "title": "使用说明",
}
nodes.append(n11)

# ---------- 连线 ----------
L1 = add_link(1, 0, 4, 0, 'IMAGE')
L2 = add_link(2, 0, 3, 0, 'IMAGE')
L3 = add_link(3, 0, 4, 2, 'FACE_MODEL')
L4 = add_link(1, 3, 5, 0, 'VIDEO')
L5 = add_link(4, 0, 6, 0, 'IMAGE')
L6 = add_link(5, 2, 6, 4, 'FLOAT')
L7 = add_link(1, 2, 6, 1, 'AUDIO')
L8 = add_link(4, 0, 7, 0, 'IMAGE')
L9 = add_link(7, 0, 8, 0, 'IMAGE')
L10 = add_link(2, 0, 9, 0, 'IMAGE')
L11 = add_link(7, 0, 9, 1, 'IMAGE')
L12 = add_link(9, 1, 10, 0, 'STRING')

set_out(n1, 0, [L1]); set_out(n1, 2, [L7]); set_out(n1, 3, [L4])
set_out(n2, 0, [L2, L10])
set_in(n3, 'images', L2); set_out(n3, 0, [L3])
set_in(n4, 'input_image', L1); set_in(n4, 'face_model', L3)
set_out(n4, 0, [L5, L8])
set_in(n5, 'video', L4); set_out(n5, 2, [L6])
set_in(n6, 'images', L5); set_in(n6, 'audio', L7); set_in(n6, 'frame_rate', L6)
set_in(n7, 'images', L8); set_out(n7, 0, [L9, L11])
set_in(n8, 'images', L9)
set_in(n9, 'image1', L10); set_in(n9, 'image2', L11); set_out(n9, 1, [L12])
set_in(n10, 'text', L12)

wf = {
    "id": "uuid-vfs-0001",
    "revision": 0,
    "last_node_id": 11,
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
