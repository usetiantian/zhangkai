"""工作流(UI 格式) -> ComfyUI API 格式 转换器。

为什么要它：导演台 11.0、换装、角色三视图 这些工作流都带子图（subgraph），
手写 API prompt 极其易错（今天踩过：子图 links 的 origin_slot 是子图口径、
KSampler 只有 1 个输出、widget 和 input 的顺序要跳过已连线的项）。

用法:
  python tools/wf2api.py <工作流.json> [--set 节点ID:输入名=值] [--out api.json]
  python tools/wf2api.py <工作流.json> --dry          # 只打印结构，不写文件
"""
import io
import json
import os
import sys

# 前端专有节点：后端不注册，转换时按需丢弃或替换成字面量
FRONTEND_ONLY = {
    "MarkdownNote", "Note", "Reroute", "PrimitiveNode",
    "Markdown", "NotePlus", "easy showAnything",
}

# litegraph 节点模式
MODE_ALWAYS, MODE_NEVER, MODE_BYPASS = 0, 2, 4


def _is_uuid(text):
    return bool(text) and len(str(text)) == 36 and str(text).count("-") == 4


def _links_map(links):
    """links 可能是 list 格式 [id,oid,osl,tid,tsl,type] 或 dict 格式 {id,origin_id,...}"""
    out = {}
    for item in links or []:
        if isinstance(item, list) and len(item) >= 6:
            out[item[0]] = {"id": item[0], "origin": item[1], "oslot": item[2],
                            "target": item[3], "tslot": item[4], "type": item[5]}
        elif isinstance(item, dict) and "id" in item:
            out[item["id"]] = {"id": item["id"], "origin": item["origin_id"],
                               "oslot": item.get("origin_slot", 0),
                               "target": item["target_id"], "tslot": item.get("target_slot", 0),
                               "type": item.get("type")}
    return out


def _spec_map(input_spec):
    """合并 required / optional，得到 {输入名: spec}。"""
    out = {}
    for bucket in ("required", "optional"):
        for name, spec in (input_spec.get(bucket) or {}).items():
            out[name] = spec
    return out


def _has_control(spec):
    """seed 之类的控件后面跟着一个「控制后动作」下拉，占两个控件值。

    判据来自后端 spec 里的 control_after_generate: true。
    """
    return bool(isinstance(spec, list) and len(spec) > 1
                and isinstance(spec[1], dict) and spec[1].get("control_after_generate"))


def _widget_slots(node):
    """节点上真正占控件值的输入，按 UI 顺序。

    返回 [(名字, 类型)]。纯 UI 控件（AUDIO_UI 之类）不占值。
    """
    out = []
    for item in node.get("inputs") or []:
        if not item.get("widget"):
            continue
        itype = str(item.get("type") or "")
        if itype.endswith("_UI"):
            continue
        out.append((item.get("name"), itype))
    return out


def _align_values(node, slots, spec_map):
    """把 widgets_values 按槽位顺序摊成 {名字: 值}。

    spec_map 用于识别 seed 的额外「控制后动作」槽。
    """
    values = list(node.get("widgets_values") or [])
    mapping = {}
    vi = 0
    for name, _itype in slots:
        if vi >= len(values):
            break
        mapping[name] = values[vi]
        vi += 1
        if _has_control(spec_map.get(name)):
            vi += 1
    return mapping


def _is_dynamic_sub(spec):
    """是否是动态 combo 类型的输入。"""
    return bool(isinstance(spec, list) and str(spec[0]).startswith("COMFY_DYNAMICCOMBO"))


def _is_autogrow(spec):
    """是否是 AUTOGROW 动态分组输入（后端收 "images.image_1" 这种扁平键）。"""
    return bool(isinstance(spec, list) and str(spec[0]).startswith("COMFY_AUTOGROW"))


def _autogrow_children(spec):
    """AUTOGROW 分组展开出的子键和最少数量。"""
    tmpl = {}
    if isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict):
        tmpl = spec[1].get("template") or {}
    names = tmpl.get("names")
    if names:
        return list(names), int(tmpl.get("min", 1) or 0)
    prefix = tmpl.get("prefix")
    if prefix:
        return ["%s%d" % (prefix, i) for i in range(int(tmpl.get("max", 0) or 0))], \
               int(tmpl.get("min", 1) or 0)
    return [], 0


def _required_ids(input_spec):
    """真正必填的输入名（把 AUTOGROW 展开成扁平的子键）。"""
    out = []
    for name, spec in ((input_spec.get("required") or {}).items()):
        if _is_autogrow(spec):
            children, minc = _autogrow_children(spec)
            for c in children[:minc]:
                out.append("%s.%s" % (name, c))
        else:
            out.append(name)
    return out


def _emitable(name, spec_map):
    """这个控件值要不要写进 API prompt。"""
    if name in spec_map:
        return True
    # 动态 combo / AUTOGROW 的子输入，后端收 "format.quality"、"images.image_1" 这种扁平键
    if "." in str(name):
        head = str(name).split(".", 1)[0]
        head_spec = spec_map.get(head)
        if head_spec and (_is_dynamic_sub(head_spec) or _is_autogrow(head_spec)):
            return True
    return False


class _Converter(object):
    """按前端 graphToPrompt 的语义把 UI 图转成 API prompt。"""

    def __init__(self, workflow, object_info):
        self.wf = workflow
        self.oi = object_info
        self.nodes = workflow.get("nodes") or []
        self.top_links = _links_map(workflow.get("links"))
        self.subgraphs = (workflow.get("definitions") or {}).get("subgraphs") or []
        self.sg_by_id = dict((str(s.get("id")), s) for s in self.subgraphs)
        self.by_id = dict((str(n.get("id")), n) for n in self.nodes)
        self.api = {}
        self.notes = []
        self._sg_out = {}     # 子图实例 id -> 其输出的 API 引用 [api_id, slot]

    # ---------- 顶层 ----------
    def run(self):
        for node in self.nodes:
            ntype = str(node.get("type"))
            if _is_uuid(ntype) and ntype in self.sg_by_id:
                continue
            if ntype in FRONTEND_ONLY:
                continue
            if int(node.get("mode", 0)) in (MODE_NEVER, MODE_BYPASS):
                continue
            spec = self.oi.get(ntype)
            if spec is None:
                self.notes.append("跳过未知节点 #%s (%s)" % (node.get("id"), ntype))
                continue
            smap = _spec_map(spec.get("input") or {})
            slots = _widget_slots(node)
            vals = _align_values(node, slots, smap)
            inputs = {}
            for name, _t in slots:
                if name in vals and _emitable(name, smap):
                    inputs[name] = vals[name]
            self.api[str(node.get("id"))] = {"class_type": ntype, "inputs": inputs}

        # 子图先展开：顶层连线要引用子图内部的输出
        for node in self.nodes:
            ntype = str(node.get("type"))
            if _is_uuid(ntype) and ntype in self.sg_by_id:
                self._expand_subgraph(node, self.sg_by_id[ntype])

        # 顶层连线
        for lk in self.top_links.values():
            src = self._origin_ref(lk["origin"], lk["oslot"])
            if src is None:
                continue
            tgt = self.by_id.get(str(lk["target"]))
            if not tgt:
                continue
            ordered = tgt.get("inputs") or []
            if lk["tslot"] >= len(ordered):
                continue
            iname = ordered[lk["tslot"]].get("name")
            aid = str(tgt.get("id"))
            if not iname or aid not in self.api:
                continue
            self.api[aid]["inputs"][iname] = src

        self._prune_broken()
        return self.api

    def _prune_broken(self):
        """剔掉必填输入没接上的孤儿节点（比如模板里留着的 Video Slice）。"""
        broken = []
        for aid, node in list(self.api.items()):
            spec = self.oi.get(node.get("class_type")) or {}
            req = _required_ids(spec.get("input") or {})
            missing = [n for n in req if n not in (node.get("inputs") or {})]
            if missing and not spec.get("output_node"):
                broken.append((aid, node.get("class_type"), missing))
        for aid, ctype, missing in broken:
            del self.api[aid]
            self.notes.append("剔除断连节点 #%s (%s)：缺少 %s" % (aid, ctype, ",".join(missing)))
        # 清掉指向被剔除节点的连线
        if broken:
            gone = set(a for a, _c, _m in broken)
            for node in self.api.values():
                for name, val in list((node.get("inputs") or {}).items()):
                    if isinstance(val, list) and len(val) == 2 and val[0] in gone:
                        node["inputs"].pop(name, None)

    def _origin_ref(self, origin, oslot, links=None, by_id=None, depth=0):
        """连线来源 -> API 引用 [api_id, slot]。"""
        key = str(origin)
        if key in self._sg_out:
            return self._sg_out[key]
        if key in self.api:
            return [key, oslot]
        # Reroute 是纯前端节点，穿过去找真正的来源
        node = self.by_id.get(key)
        if node is not None and str(node.get("type")) == "Reroute" and depth < 16:
            ins = node.get("inputs") or []
            if ins and ins[0].get("link") is not None:
                lk = self.top_links.get(ins[0]["link"])
                if lk:
                    return self._origin_ref(lk["origin"], lk["oslot"], depth=depth + 1)
        return None

    # ---------- 子图 ----------
    def _expand_subgraph(self, node, sg):
        inst_id = str(node.get("id"))
        sg_links = _links_map(sg.get("links"))
        sg_inputs = sg.get("inputs") or []
        inst_inputs = node.get("inputs") or []

        # 接口槽位 -> 父图连线（父图连了才透传）
        iface_links = {}
        for idx, iface in enumerate(sg_inputs):
            name = iface.get("name")
            for item in inst_inputs:
                if item.get("name") == name and item.get("link") is not None:
                    lk = self.top_links.get(item["link"])
                    if lk:
                        iface_links[idx] = self._origin_ref(lk["origin"], lk["oslot"])
                    break

        # 实例节点的控件值 -> 接口槽位
        # 子图接口没有 control_after_generate，所以一个槽位对一个值
        inst_slots = _widget_slots(node)
        inst_vals = _align_values(node, inst_slots, {})
        slot_value = {}
        for idx, iface in enumerate(sg_inputs):
            name = iface.get("name")
            if name in inst_vals:
                slot_value[idx] = inst_vals[name]

        # 内部节点
        for inner in sg.get("nodes") or []:
            itype = str(inner.get("type"))
            if itype in FRONTEND_ONLY:
                continue
            if int(inner.get("mode", 0)) in (MODE_NEVER, MODE_BYPASS):
                continue
            spec = self.oi.get(itype)
            if spec is None:
                self.notes.append("跳过子图内未知节点 %s:%s (%s)"
                                  % (inst_id, inner.get("id"), itype))
                continue
            smap = _spec_map(spec.get("input") or {})
            slots = _widget_slots(inner)
            vals = _align_values(inner, slots, smap)
            inputs = {}
            for name, _t in slots:
                if name in vals and _emitable(name, smap):
                    inputs[name] = vals[name]

            for item in inner.get("inputs") or []:
                if item.get("link") is None:
                    continue
                lk = sg_links.get(item["link"])
                if not lk:
                    continue
                name = item.get("name")
                origin = lk["origin"]
                if origin == -10:
                    if lk["oslot"] in iface_links:
                        inputs[name] = iface_links[lk["oslot"]]
                    elif lk["oslot"] in slot_value:
                        inputs[name] = slot_value[lk["oslot"]]
                elif origin == -20:
                    continue
                else:
                    ref = self._inner_origin_ref(inst_id, sg, sg_links, origin, lk["oslot"])
                    if ref is not None:
                        inputs[name] = ref

            self.api["%s:%s" % (inst_id, inner.get("id"))] = {
                "class_type": itype, "inputs": inputs}

        # 子图输出：找指向 -20 的内部连线
        for lk in sg_links.values():
            if lk["target"] == -20 and lk["origin"] != -10:
                self._sg_out[inst_id] = ["%s:%s" % (inst_id, lk["origin"]), lk["oslot"]]

    def _inner_origin_ref(self, inst_id, sg, sg_links, origin, oslot, depth=0):
        """子图内部连线来源 -> API 引用。Reroute 之类的纯前端节点要穿过去。"""
        key = str(origin)
        node = None
        for n in sg.get("nodes") or []:
            if str(n.get("id")) == key:
                node = n
                break
        if node is None:
            return None
        ntype = str(node.get("type"))
        if ntype == "Reroute":
            if depth >= 16:
                return None
            ins = node.get("inputs") or []
            if ins and ins[0].get("link") is not None:
                lk = sg_links.get(ins[0]["link"])
                if lk:
                    return self._inner_origin_ref(inst_id, sg, sg_links,
                                                 lk["origin"], lk["oslot"], depth + 1)
            return None
        if ntype in FRONTEND_ONLY:
            return None
        if int(node.get("mode", 0)) in (MODE_NEVER, MODE_BYPASS):
            return None
        return ["%s:%s" % (inst_id, key), oslot]


def convert(workflow, object_info, overrides=None):
    """把一个 UI 工作流转成 API prompt。返回 (prompt, 提示信息列表)。"""
    conv = _Converter(workflow, object_info)
    api = conv.run()
    for node_id, kv in (overrides or {}).items():
        if node_id in api:
            api[node_id]["inputs"].update(kv)
    return api, conv.notes


def check(prompt, object_info):
    """不提交、不烧 GPU，只校验 API prompt 的合法性。返回错误列表。"""
    errs = []
    outputs = {}
    for aid, node in prompt.items():
        spec = object_info.get(node["class_type"])
        if spec is None:
            errs.append("节点 %s 类型未注册: %s" % (aid, node["class_type"]))
            continue
        outputs[aid] = spec.get("output") or []
        req = (spec.get("input") or {}).get("required") or {}
        for name, spec_item in req.items():
            if name in node["inputs"]:
                continue
            kind = spec_item[0] if isinstance(spec_item, list) and spec_item else ""
            if "AUTOGROW" in str(kind) or "DYNAMIC" in str(kind):
                continue      # 动态输入由前端运行期决定，API 静态校验跳过
            errs.append("节点 %s(%s) 缺少必填输入 %s" % (aid, node["class_type"], name))
    for aid, node in prompt.items():
        for name, val in (node.get("inputs") or {}).items():
            if not (isinstance(val, list) and len(val) == 2 and isinstance(val[1], int)):
                continue
            src, slot = val
            if src not in prompt:
                errs.append("节点 %s 的输入 %s 指向不存在的节点 %s" % (aid, name, src))
                continue
            outs = outputs.get(src) or []
            if slot >= len(outs):
                errs.append("节点 %s 的输入 %s 指向 %s 的输出槽 %d（该节点只有 %d 个输出）"
                            % (aid, name, src, slot, len(outs)))
    return errs


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    wf_path = args[0]
    dry = "--dry" in args
    do_check = "--check" in args
    out_path = None
    overrides = {}
    for i, a in enumerate(args):
        if a == "--out" and i + 1 < len(args):
            out_path = args[i + 1]
        if a == "--set" and i + 1 < len(args):
            node_id, rest = args[i + 1].split(":", 1)
            key, val = rest.split("=", 1)
            try:
                val = json.loads(val)
            except Exception:
                pass
            overrides.setdefault(node_id, {})[key] = val
    base = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
    oi_path = args[args.index("--oi") + 1] if "--oi" in args else "_oi_now.json"
    if not os.path.exists(oi_path):
        import urllib.request
        with urllib.request.urlopen(base + "/object_info", timeout=60) as r:
            oi = json.load(r)
    else:
        oi = json.load(io.open(oi_path, encoding="utf-8"))
    wf = json.load(io.open(wf_path, encoding="utf-8"))
    prompt, notes = convert(wf, oi, overrides)
    for n in notes:
        print("  ~", n)
    if dry:
        print("节点数:", len(prompt))
        for aid, n in prompt.items():
            print(" ", aid, n["class_type"], json.dumps(n["inputs"], ensure_ascii=False)[:150])
        return 0
    if do_check:
        errs = check(prompt, oi)
        print("节点数:", len(prompt), "| 校验错误:", len(errs))
        for e in errs[:20]:
            print("  !", e)
        return 0 if not errs else 1
    dest = out_path or (os.path.splitext(wf_path)[0] + "_api.json")
    io.open(dest, "w", encoding="utf-8").write(json.dumps({"prompt": prompt}, ensure_ascii=False, indent=1))
    print("已生成:", dest, "| 节点数:", len(prompt))
    return 0


if __name__ == "__main__":
    sys.exit(main())

