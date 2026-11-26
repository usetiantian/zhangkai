"""古风国漫漫剧流水线：小说 -> 剧本 -> 官方 H3 分镜 -> 视频。

用法:
  python tools/guofeng_manga.py script     <novel.txt>   [-o out.txt] [--duration 15]
  python tools/guofeng_manga.py storyboard <script.txt>  [-o out.txt]
  python tools/guofeng_manga.py segments   <board.txt>   [-o segments.json]
  python tools/guofeng_manga.py video      <segments.json> [--duration 8] [--dry]
  python tools/guofeng_manga.py all        <novel.txt>   [--duration 15] [--dry]

依赖:
  - ComfyUI 跑在 127.0.0.1:8188，已装 ComfyUI-H3-Director 插件
  - 导演台的 API 设置里已配好 LLM（POST /h3director/api_config）
  - tools/wf2api.py 能把导演台11.0 工作流转成 API prompt

设计要点:
  - 系统提示词、分镜解析全部复用插件前端自己的函数（tools/h3_js.mjs 抽取），
    不自己重写，避免插件升级后行为漂移。
  - 风格锚定靠 global_prompt + 提示词里的风格句双重保证。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
DIRECTOR_WF = os.environ.get(
    "DIRECTOR_WF",
    "D:/ComfyUI_windows_portable/ComfyUI/user/default/workflows/导演台11.0.json")

# 古风国漫动漫风格锚定：global_prompt 与提示词里都会带
GUOFENG_STYLE = (
    "国产玄幻动漫风格（《遮天》《完美世界》《仙逆》那一挂）：高饱和度厚涂上色，精细锐利描边，"
    "深邃明暗对比与体积光，人物边缘轮廓光，高饱和玄幻配色（暗金、青蓝、赤金、月白、紫电），"
    "画面带灵气粒子与法术光效，人物七点五头身写实比例，五官精致。"
    "禁止平涂赛璐璐、暖黄复古色调、老电影质感、水墨晕染、颗粒感、复古滤镜、"
    "80年代动画感、Q版幼态、真人实拍、3D写实，以及任何现代物品。"
)

# 分镜规范（2026-11-26 定稿）
# 来源：short-drama-director/references/visual-grammar.md + 本地 A/B/C/D 对照实验的结论。
#
# ⚠️ 实验结论（同一段素材、只换分镜、出片肉眼评比）：
#    胜出的不是"镜头最多/最电影"的那版，而是**镜头数不变 + 台词镜时长够 + 运镜写具体**的那版。
#    镜头更多的那两版（加顶视全景、加门缝空镜）反而被判"画面逻辑有瑕疵"。
#    所以这里明确禁止为了电影感插入空镜或跳轴线。
SHOT_RULES = """
【分镜规范 — 严格照做】
1. 运镜写成完整句法：初始构图 + 触发 + 路径/幅度/速度 + 终止构图 + 戏剧结果。
   例：木桶完全离开井口时，摄影机以极缓慢的速度向前推进约半米，终止构图是林渺侧脸与井口同框，让观众先认出院落，再认出人。
   禁止只写"镜头缓慢推进"这种没有触发、没有落点的运镜标签。
2. 景别按**叙事功能**选，不按尺寸标签：建立环境用全景，表演与关系用中景/中近景，
   不可忽视的微表情或关键证据用近景/特写。景别要有层级：建立常态之后，
   只有信息或权力升级才靠近，高潮后退远表达代价。
3. 写明机位与焦段，并说明角度变化改变了什么观看关系：
   平视 eye（观察、不预判）/ 俯视 high（受制、暴露）/ 仰视 low（支配、决心）/
   顶视 overhead（图案、困局、疏离）/ 倾斜 dutch（秩序失衡）/ 贴地 ground（脚步、逼近）。
   焦段倾向：18-24mm 扩空间与速度，28-35mm 兼顾人物与竖屏纵深，40-50mm 自然克制，
   65-85mm 压缩空间突出微表情，100mm+ 窥视或细节。
4. **一个 Shot 只承担一个主要动作**。不要把眨眼、起步、落地、开门拆成亚秒镜头，
   也不要在一个 Shot 里塞两个以上互不相干的主要动作。
5. **镜头连贯优先于镜头数量**。不要插入与叙事无关的空镜（只有门缝、只有地面、只有特写），
   不要突然换轴线或跳视角，不要改变观众已经建立的空间关系。宁可少一个镜头，
   也不要让观众看不懂人在哪。
8. **镜头长度由叙事决定，不由默认习惯决定。** 先判断这场戏"要不要一口气讲完"：
   - 情绪需要连续的空间感与时间感（一口气的等待、压迫、发现、行云流水的动作、
     人物从进门走到亮起来）→ 用**一个连续镜头**走完，中间不切；
     运镜写清"起幅 — 触发 — 路径/幅度/速度 — 终止构图 — 戏剧结果"。
   - 需要换视角、换信息、情绪要断 → 才切镜。
   - **不要所有镜头都等长**。等长就说明没有逐镜判断。镜长应随戏走：
     冲突紧的戏短、等待的戏长、情绪转折处给一个明显更长的镜头。
     如果整场戏的镜头长度几乎一样，就重新按戏的内容重排。
6. **台词时长自检**：每个 <d> 台词的汉字数（含标点）必须 ≤ 该 Shot 秒数 × 4；
   同时按不超过 3.5 字/秒 预留余量（一个 21 字的句子至少要 6 秒）。
   台词放不下时**加长这个 Shot**，不要塞进别的 Shot 里。
7. 绝对时间戳严格递增，最后一个 Shot 的结束点正好等于目标总时长。
9. **长镜头写法（2026-11-26 实测通过：14 秒一镜到底，人脸/服装/光影全程一致）**
   整段戏一口气讲完时（等待、发现、压迫、行云流水的动作、从进门走到亮起来），
   写成**一个** [Shot N]，把整段时长给足（10~14 秒），运镜是一条连贯的完整句法：
   **起幅**（在哪、看见什么）→ **触发**（什么让镜头动起来）→ **路径/幅度/速度**
   → **终止构图**（最后看到什么）→ **戏剧结果**（观众此刻该感到什么）。
   例：起幅是门框内的一线斜阳切过斑驳土墙，纸窗透进的暖光里浮着细尘；摄影机沿着这道光带
   缓缓推入，掠过木桌上磕出缺口的粗瓷碗和带铜锁的旧木箱，最后停在床沿的林渺身上 ——
   他正低着头，把腰间的青色小葫芦解下来托在掌心。他抬眼的一瞬摄影机停止推进，
   稳稳停在能同时看清他的眼睛与掌心青光的距离，让这一口气从门口一直走到亮起来，
   中间一次都不切。
   ⚠️ 长镜头里**不要中途换主体或换场景**，换了就不是长镜头了。
   ⚠️ 长镜头不等于慢：镜头在动、主体在动，只是没有切。
"""

# 声音设计规范（2026-11-26 定稿）
# 来源：short-drama-production/references/sound-production.md
# ⚠️ H3 的硬限制：**最多 3 条音频参考** → 一段里最多稳定绑定 3 套音色，
#    4 人以上对白场要拆成双人/三人镜头，或把次要角色放画外用后期声音。
# ⚠️ 之前的段表每段只挂一个音色且 prompt 里一条 <Audio N> 绑定都没有
#    → 父亲的台词用了别人的嗓子、老道士用了少年的声音（2026-11-26 查出）。
SOUND_RULES = """
【声音设计 — 严格照做】
1. 分四层写，不要只写一句"同步声音"：
   - 对白：谁在说话（必须写出说话人和音色绑定标记）
   - 环境：空间底噪与持续环境（风、水、人声、远处）
   - 拟音 foley：脚步、衣料、道具、冲击声——**每个 Shot 都要写具体到材质**：
     例"粗麻井绳被攥紧的干涩吱嘎声，井绳在石槽里磨过的沙沙声，木桶铁圈刮过井沿的短促金属声"
   - 配乐：默认 N/A（每段各自生成主题音乐会旋律/调性/速度跳变，统一配乐放后期）
2. 音效要写**音场、质感、远近、节奏**：干涩的/沙哑的/短促的/低沉的；近处/远处/画外。
3. **静默设计**：关键台词前留半秒静默，或用"某声突然停止"把下一句话托起来。
   安静的留白比加音效更能让观众集中。
4. **说话人必须写清楚是谁、以及他的嗓音特征**：写成"林守田（苍老沙哑的嗓音）开口：<d>…</d>"。
   ⚠️ 这里**不要**写 <Subject N> 或 <Audio N> —— 那是导演台在重写成 Ref2VA 时自动绑定的，
      你自己写会被判为格式错误。绑定关系由"段表挂的音色文件"决定。
5. 一段里超过 3 个说话人时：把次要角色放画外（画外音仍写清楚是谁），
   或把这一段拆成两个镜头。
"""

# 导演台节点在 API prompt 里的 id（wf2api 保留 UI 节点 id）
STUDIO_NODE = "13"
NL2 = chr(10) + chr(10)


def _post(path, payload, timeout=900):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(COMFY + path, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _get(path, timeout=60):
    with urllib.request.urlopen(COMFY + path, timeout=timeout) as resp:
        return json.load(resp)


def sys_prompt(mode, asset_context="（参考资产库为空）"):
    """从导演台前端抽系统提示词。"""
    out = subprocess.run(
        ["node", os.path.join(HERE, "h3_prompts.mjs"), mode, asset_context],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError("取系统提示词失败: " + out.stderr[:500])
    return out.stdout


def ai_call(system, user, max_tokens=4000):
    """走导演台的 LLM 接口。"""
    res = _post("/h3director/ai_prompt", {
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
    })
    if not res.get("ok"):
        raise RuntimeError("AI 生成失败: " + str(res.get("error")))
    return res.get("content") or ""


def make_script(novel, duration=0, asset_context="（参考资产库为空）", context=""):
    """小说 -> 可拍摄剧本。"""
    user = novel.strip()
    if duration:
        user = "目标总时长：%d秒" % duration + NL2 + user
    if context:
        user = context.strip() + NL2 + NL2 + user
    user = user + NL2 + NL2 + "风格要求：" + GUOFENG_STYLE
    return ai_call(sys_prompt("create_script", asset_context), user)



# ---------------- 分镜时间重排与自检（2026-11-26） ----------------
# 病根：导演台规则「台词字数 ≤ 该 Shot 秒数 × 4」，但 LLM 常给台词镜只留 3 秒
# → H3 念不完，后半段画面停住（实测相邻帧差异掉到 12/255，静止）。
# 这里做**确定性**修正，不依赖 LLM 自觉：按台词字数给每个 Shot 算出最小时长，
# 再把富余时间按原比例摊回去，总时长守恒（导演台的守恒门禁不能破）。
_SHOT_AT = re.compile(r'At\s+(\d+):(\d+):(\d+(?:\.\d+)?)')
_SHOT_HEAD = re.compile(r'\[Shot\s+(\d+)\]')
_DIALOG = re.compile(r'<d>\[Chinese\](.*?)</d>', re.S)


def _sec(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def _fmt(t):
    t = round(t, 3)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    return "%02d:%02d:%06.3f" % (h, m, t % 60)


def split_shots(board):
    """把官方分镜正文切成 [(序号, 整块文本)]。只处理 integrated_multimodal_description 段。"""
    # 两种格式都要认：
    #   base 格式（导演台 AI 分镜原文）：integrated_multimodal_description:
    #   Ref2VA 格式（段表里每段的 prompt）：detailed_description:
    i = board.find("integrated_multimodal_description:")
    if i < 0:
        i = board.find("detailed_description:")
    if i < 0:
        return board, [], board
    j = board.find("overall_soundscape:", i)
    if j < 0:
        j = len(board)
    head, desc, tail = board[:i], board[i:j], board[j:]
    starts = [(int(m.group(1)), m.start()) for m in _SHOT_HEAD.finditer(desc)]
    if not starts:
        return head, [], tail
    shots = []
    for k, (num, st) in enumerate(starts):
        end = starts[k + 1][1] if k + 1 < len(starts) else len(desc)
        body = desc[st:end]
        if k == 0 and st > 0:
            body = desc[:st] + body      # 第一个 Shot 之前的内容别丢
        shots.append([num, body])
    return head, shots, tail


def shot_chars(body):
    return sum(len(x) for x in _DIALOG.findall(body))


def rebalance_shots(board, rate=3.5, floor=1.5, total=None):
    """按台词字数重排各 Shot 时长，总时长守恒。返回 (新分镜, 报告)。"""
    head, shots, tail = split_shots(board)
    if not shots:
        return board, {"ok": False, "msg": "没解析到 Shot"}
    # 当前时长：第 1 个从 0 开始，其余按 At 差值
    cur = []
    for idx, (num, body) in enumerate(shots):
        m = _SHOT_AT.search(body)
        cur.append(_sec(*m.groups()) if m else 0.0)
    if not total:
        total = storyboard_total(board)
    durs = []
    for idx in range(len(shots)):
        start = cur[idx]
        end = cur[idx + 1] if idx + 1 < len(shots) else total
        durs.append(max(0.0, end - start))
    mins = []
    for idx, (num, body) in enumerate(shots):
        c = shot_chars(body)
        need = c / rate if c else 0.0
        mins.append(max(durs[idx], need, floor if durs[idx] > 0 else 0.0))
    sum_min = sum(mins)
    report = {"ok": True, "shots": len(shots), "total": total, "sum_min": round(sum_min, 2),
              "over": [], "moved": []}
    if sum_min > total + 1e-6:
        # 装不下 → 不是分镜能修的，得回剧本层拆场次/减台词
        report["ok"] = False
        report["msg"] = "台词总需求 %.1f 秒 > 总时长 %.1f 秒，需回剧本层拆场次" % (sum_min, total)
        for idx, (num, body) in enumerate(shots):
            if mins[idx] > durs[idx] + 1e-6:
                report["over"].append({"shot": num, "need": round(mins[idx], 2),
                                       "have": round(durs[idx], 2)})
        return board, report
    # 富余时间按原比例摊回去
    slack = total - sum_min
    new_durs = []
    for idx in range(len(shots)):
        share = (durs[idx] / total) if total > 0 else (1.0 / len(shots))
        new_durs.append(mins[idx] + slack * share)
    # 修正累计误差
    acc = 0.0
    for idx in range(len(new_durs) - 1):
        new_durs[idx] = round(new_durs[idx], 3)
        acc += new_durs[idx]
    new_durs[-1] = round(total - acc, 3)
    # 写回 At 时间戳
    out = []
    t = 0.0
    for idx, (num, body) in enumerate(shots):
        nb = body
        if idx > 0:
            nb = _SHOT_AT.sub("At " + _fmt(t) + ",", nb, count=1)
        out.append(nb)
        if abs(new_durs[idx] - durs[idx]) > 0.05:
            report["moved"].append({"shot": num, "from": round(durs[idx], 2), "to": round(new_durs[idx], 2)})
        t += new_durs[idx]
    new_desc = "".join(out)
    return head + new_desc + tail, report


def _shot_span_last(body):
    """最后一个 Shot 的默认跨度（没有下一个 At 时用）。"""
    return 6.0


def storyboard_total(board):
    """分镜声明的总时长：优先 manifest，其次最后一个 At + 默认跨度。"""
    m = re.search(r"source_total_duration_seconds:\s*([\d.]+)", board)
    if m:
        return float(m.group(1))
    head, shots, tail = split_shots(board)
    if not shots:
        return 0.0
    last = shots[-1][1]
    mm = _SHOT_AT.search(last)
    return (_sec(*mm.groups()) if mm else 0.0) + _shot_span_last(last)


def audit_storyboard(board):
    """检查台词时长是否合规（不修改，只报告）。"""
    head, shots, tail = split_shots(board)
    if not shots:
        return []
    cur = []
    for num, body in shots:
        m = _SHOT_AT.search(body)
        cur.append(_sec(*m.groups()) if m else 0.0)
    total = storyboard_total(board)
    bad = []
    for idx in range(len(shots)):
        start = cur[idx]
        end = cur[idx + 1] if idx + 1 < len(shots) else total
        d = end - start
        c = shot_chars(shots[idx][1])
        if c and c > d * 4:
            bad.append({"shot": shots[idx][0], "chars": c, "sec": round(d, 2), "limit": round(d * 4, 2)})
    return bad



def audit_uniformity(board, tol=0.6, min_shots=3):
    """检测「机械等长」：镜头长度几乎一样 = 分镜没做逐镜判断。

    为什么要查这个：张凯的原话「不是特意要长镜头，是一句剧情需要，也是导演的功底」
    —— 长镜头是判断的结果，不是要追求的技术。判断的病征恰恰是**长度一样**：
    清一色 6 秒/8 秒说明 LLM 套了默认习惯，没在想这场戏要多久。
    """
    head, shots, tail = split_shots(board)
    if not shots or len(shots) < min_shots:
        return {"uniform": False, "msg": "镜头太少，不判", "durations": []}
    cur = []
    for num, body in shots:
        m = _SHOT_AT.search(body)
        cur.append(_sec(*m.groups()) if m else 0.0)
    total = storyboard_total(board)
    durs = []
    for i in range(len(shots)):
        end = cur[i + 1] if i + 1 < len(shots) else total
        durs.append(round(max(0.0, end - cur[i]), 2))
    # 最常见的长度及其占比
    from collections import Counter
    cnt = Counter(round(d, 1) for d in durs)
    common, n = cnt.most_common(1)[0]
    ratio = n / float(len(durs))
    return {"uniform": ratio >= tol, "ratio": round(ratio, 2), "common_len": common,
            "n": n, "total_shots": len(durs), "durations": durs,
            "msg": ("%d/%d 个镜头都是 %.1f 秒（%.0f%%）—— 等长，说明没逐镜判断"
                    % (n, len(durs), common, ratio * 100)) if ratio >= tol
                   else "镜头长度有变化（最长 %.1f / 最短 %.1f 秒），判断过" % (max(durs), min(durs))}


def audit_uniformity_beats(task, tol=0.6):
    """场次层的机械等长检测（同上，作用在分镜任务书上）。"""
    head, blocks = beat_blocks(task)
    if not blocks:
        return {"uniform": False, "msg": "没解析到场次", "durations": []}
    durs = []
    for num, block in blocks:
        m = _BEAT_TIME.search(block)
        if m:
            durs.append(round(float(m.group(2)) - float(m.group(1)), 2))
    if len(durs) < 3:
        return {"uniform": False, "msg": "场次太少，不判", "durations": durs}
    from collections import Counter
    cnt = Counter(round(d, 1) for d in durs)
    common, n = cnt.most_common(1)[0]
    ratio = n / float(len(durs))
    return {"uniform": ratio >= tol, "ratio": round(ratio, 2), "common_len": common,
            "n": n, "total_shots": len(durs), "durations": durs,
            "msg": ("%d/%d 个场次都是 %.1f 秒（%.0f%%）—— 等长，说明没逐场判断"
                    % (n, len(durs), common, ratio * 100)) if ratio >= tol
                   else "场次长度有变化（最长 %.1f / 最短 %.1f 秒），判断过" % (max(durs), min(durs))}

def audit_segments(segments):
    """检查导演台段表里每条台词的时长（出片前自检用）。"""
    bad = []
    for si, seg in enumerate(segments or []):
        t = seg.get("prompt", "") or ""
        dur = float(seg.get("duration") or 0)
        ats = [float(x) for x in re.findall(r"At\s+\d+:\d+:([\d.]+)", t)]
        bounds = [0.0] + ats + [dur]
        parts = re.split(r"\[Shot\s+\d+\]", t)[1:]
        for j, body in enumerate(parts):
            if j + 1 >= len(bounds):
                break
            d = bounds[j + 1] - bounds[j]
            for line in body.split("\n"):
                for m in re.finditer(r"<d>\[Chinese\](.*?)</d>", line):
                    n = len(m.group(1))
                    if n > d * 4:
                        bad.append({"seg": si + 1, "shot": j + 1, "chars": n,
                                    "sec": round(d, 2), "limit": round(d * 4, 2)})
    return bad

def make_storyboard(script, asset_context="（参考资产库为空）", context="", rebalance=True):
    """剧本 -> 官方 H3 分镜（带运镜规范 + 确定性时间重排）。"""
    user = script.strip()
    if context:
        user = context.strip() + NL2 + NL2 + user
    user = user + NL2 + NL2 + "风格要求：" + GUOFENG_STYLE
    user = user + NL2 + NL2 + SHOT_RULES
    user = user + NL2 + NL2 + SOUND_RULES
    board = ai_call(sys_prompt("create_storyboard", asset_context), user)
    if rebalance:
        fixed, rep = rebalance_shots(board)
        if rep.get("moved"):
            print("  时间重排:", rep["moved"])
        if not rep.get("ok"):
            print("  ⚠️ 时间重排装不下:", rep.get("msg"), rep.get("over"))
        elif fixed != board:
            board = fixed
    return board


BEAT_RULES = """
【输出格式要求 — 严格照做，不要任何解释、小标题或 Markdown】
0. ★ 先算预算再写（不要凭感觉写）：
   - 全片台词总字数（所有场次所有台词之和，含标点）**不得超过 目标总时长 × 3.5**
     （例：300 秒的戏 → 全片台词合计 ≤ 1050 字；慢念按 ×3 算 → ≤ 900 字）
   - 场次数 ≈ 目标总时长 ÷ 12（300 秒 → 约 25 个场次），不要写成十几个大场次
   - 每个场次的时长随戏变化：冲突紧的 8~12 秒，等待/情绪的 18~28 秒，
     **不要清一色 24 秒**
   - 每个场次里所有台词之和 ≤ 该场次秒数 × 3
   预算不够就**删台词和情节**，不要压缩语速来硬塞。
1. 第一行必须且只能写：目标总时长：X秒（X 就是给定的目标总时长）
2. 之后每个场次严格按下面五行写，场次之间空一行：
场次N
起始秒–结束秒
场景与时间：…
出场人物：…
△动作描述…
角色名：台词
3. 所有场次的时间首尾相接，第一个从 0.000 秒开始，最后一个结束正好等于 X 秒。
4. ★ 台词预算按**场次总字数**算，不是按单句算：
   一个场次里**所有台词的汉字数之和（含标点）**必须不超过该场次秒数乘 4
   （慢念请按秒数乘 3 留余量）。H3 念白共享同一段时间，逐句合规但总量超标
   一样念不完 —— 会口型错位、念断。
   超了就把台词改短，或者把这一场的时间拉长。台词短促、克制、有信息量，不要长篇大论。
5. 每个场次只承担一个主要动作，不要在一个场次里塞多个事件。
6. 场景与时间要写出古风场景的具体元素：建筑形制、器物、光线、天气、人物站位。
   全片不得出现任何现代物品（玻璃幕墙、水泥、电线杆、汽车、塑料、拉链、眼镜、灯具等）。
7. 人物外貌与服装必须与上面的定妆逐字一致，不要自行更改发型或衣服颜色。
7b. ★ 台词和内心暗想必须分开：
    - 说出口的台词写「角色名：台词」
    - 内心独白写「（内心独白）……」，并在动作里注明人物闭口不言，只用表情和眼神演出
    - 旁白写「旁白（画面无人开口）：……」
    - 内心独白和旁白不算"台词"，不要写成「角色名：……」的形式。
    - 暗想的字数同样受 秒数×4 约束。
8. 场面要有力度，不要平淡。每场动作必须写清：
   - 发力的方向与速度（猛地、骤然、瞬间、一点点碾过去）
   - 冲击的物理反馈（青石地面龟裂、尘土被气浪推开、衣袍被罡风撕开、
     木桶撞墙碎裂、灯笼摇晃、瓦片震落、碗中水面震出涟漪）
   - 镜头怎么跟（低机位贴地仰拍、快速推近到眼睛特写、环绕跟拍、
     冲击瞬间定格、慢动作拉出全景收尾）
   - 高潮场次要写爆点：灵光爆开、五色光环旋转压缩、符文炸成光屑、
     剑气拖出长痕、身影化作流光、碎石悬空又落下
9. 场景必须写到材质、层次、光源、氛围、规模感，不能只写地点名字。
   例如"县衙东院灵根测试场"要展开成：青砖院墙、墙头飞檐翘角檐角挂铜铃、
   院中青石高台台面刻古篆纹、台上半人高乳白色测灵玉玉质温润半透明内部有流光游走、
   台下黑压压乡民、空气里有香火与尘土微粒、日光斜切过院墙落在高台上。
10. 道具要点名并写质感与来历：不要写"一个葫芦"，要写"拇指大小的青色小葫芦，
    温润青玉质地，用旧红绳系着，葫芦口有细微荧光"。
11. ★ Shot 数量必须受控（导演台会按 15 秒一个生成段切分，Shot 太密会超时）：
    每 15 秒安排 3–5 个 Shot，全片 Shot 总数不超过 20 个；每个 Shot 2–6 秒；
    最后一个 Shot 的结束时间必须正好等于目标总时长。
    禁止为了"画面好看"加拍与剧情无关的镜头，禁止把一个动作拆成多镜慢放。
12. 只输出剧本本身，不要写解释、不要思考过程、不要代码围栏。
"""



# ---------------- 场次（beat）时间重排（2026-11-26） ----------------
# 病根：场次时长在分镜任务书里是**写死**的（"0.000–6.000秒"），
# LLM 只能照抄，没有重分配的余地 → 台词装不下时必然念不完。
# 这一层重排才真正能动时间；分镜层（rebalance_shots）只是兜底。
_BEAT_HEAD = re.compile(r"(?m)^场次\s*(\d+)\s*$")
_BEAT_TIME = re.compile(r"(?m)^(\d+(?:\.\d+)?)\s*[–\-—~至]\s*(\d+(?:\.\d+)?)\s*(?:秒)?\s*$")
_BEAT_LINE = re.compile(r"(?m)^([^\n：]{1,8})：([^\n]+)$")


def beat_blocks(task):
    """把分镜任务书切成 [(场次号, 整块文本)]，保留表头。"""
    heads = [(int(m.group(1)), m.start()) for m in _BEAT_HEAD.finditer(task)]
    if not heads:
        return task, []
    head = task[:heads[0][1]]
    out = []
    for k, (num, st) in enumerate(heads):
        end = heads[k + 1][1] if k + 1 < len(heads) else len(task)
        out.append([num, task[st:end]])
    return head, out


def beat_dialogue_chars(block):
    """场次里的台词字数（排除「场景与时间：」「出场人物：」这类字段）。"""
    n = 0
    for m in _BEAT_LINE.finditer(block):
        who, what = m.group(1).strip(), m.group(2).strip()
        if who in ("场景与时间", "出场人物", "目标总时长"):
            continue
        n += len(what)
    return n


def rebalance_beats(task, total=None, rate=3.5):
    """按台词字数重排各场次时长，总时长守恒。返回 (新任务书, 报告)。"""
    head, blocks = beat_blocks(task)
    if not blocks:
        return task, {"ok": False, "msg": "没解析到场次"}
    m = re.search(r"目标总时长：\s*(\d+(?:\.\d+)?)\s*秒", task)
    if total is None:
        total = float(m.group(1)) if m else None
    durs, chars = [], []
    for num, block in blocks:
        tm = _BEAT_TIME.search(block)
        durs.append(float(tm.group(2)) - float(tm.group(1)) if tm else 0.0)
        chars.append(beat_dialogue_chars(block))
    if total is None:
        total = sum(durs)
    mins = [max(durs[i], chars[i] / rate if chars[i] else 0.0) for i in range(len(blocks))]
    sum_min = sum(mins)
    rep = {"ok": True, "total": total, "sum_min": round(sum_min, 2),
           "over": [], "moved": [], "beats": len(blocks)}
    if sum_min > total + 1e-6:
        rep["ok"] = False
        rep["msg"] = ("台词总需求 %.1f 秒 > 目标总时长 %.1f 秒：要么加长整集，"
                      "要么砍台词（青葫道人那两句占全片 30%%）" % (sum_min, total))
        for i in range(len(blocks)):
            if mins[i] > durs[i] + 1e-6:
                rep["over"].append({"beat": blocks[i][0], "chars": chars[i],
                                    "need": round(mins[i], 2), "have": round(durs[i], 2)})
        return task, rep
    slack = total - sum_min
    new = []
    for i in range(len(blocks)):
        share = (durs[i] / total) if total > 0 else (1.0 / len(blocks))
        new.append(mins[i] + slack * share)
    acc = 0.0
    for i in range(len(new) - 1):
        new[i] = round(new[i], 3)
        acc += new[i]
    new[-1] = round(total - acc, 3)
    t = 0.0
    for i, (num, block) in enumerate(blocks):
        nb = block
        tm = _BEAT_TIME.search(nb)
        if tm:
            nb = nb[:tm.start()] + ("%.3f–%.3f秒" % (t, t + new[i])) + nb[tm.end():]
        blocks[i][1] = nb
        if abs(new[i] - durs[i]) > 0.05:
            rep["moved"].append({"beat": num, "chars": chars[i],
                                 "from": round(durs[i], 2), "to": round(new[i], 2)})
        t += new[i]
    return head + "".join(b[1] for b in blocks), rep


def audit_beats(task):
    """检查每个场次的台词是否装得下（只报告）。"""
    head, blocks = beat_blocks(task)
    bad = []
    for num, block in blocks:
        tm = _BEAT_TIME.search(block)
        if not tm:
            continue
        d = float(tm.group(2)) - float(tm.group(1))
        c = beat_dialogue_chars(block)
        if c and c > d * 4:
            bad.append({"beat": num, "chars": c, "sec": round(d, 2), "limit": round(d * 4, 2)})
    return bad


# ---------------- 音色绑定与体检（2026-11-26） ----------------
_VOICE_TABLE_CANDIDATES = [
    os.path.join(ROOT, "manga", "渺渺仙途", "00_素材", "音色", "音色表.json"),
    os.path.join(ROOT, "..", "manga", "渺渺仙途", "00_素材", "音色", "音色表.json"),
]
_DIALOG_TAG = re.compile(r"<d>\[Chinese\](.*?)</d>", re.S)
_NAME_COLON = re.compile(r"([^\s，。！？；：、,.!?;:\n（）()【】\[\]<>\"]{1,8})[：:]\s*$")


def voice_table(path=None):
    """角色 -> 音色文件名。没有音色表就返回空表。"""
    cands = [path] if path else _VOICE_TABLE_CANDIDATES
    for p in cands:
        if not p or not os.path.exists(p):
            continue
        try:
            d = json.load(io.open(p, encoding="utf-8"))
            t = {k: v for k, v in d.items() if isinstance(v, str)}
            if t:
                return t
        except Exception:
            continue
    return {}


def character_names(ctx=""):
    """从素材上下文里抽角色名（「林渺（十六岁少年男性…）」这种形式）。"""
    out = []
    for m in re.finditer(r"([\u4e00-\u9fff]{2,4})\uff08", ctx or ""):
        n = m.group(1)
        if n not in out:
            out.append(n)
    return out


def _clean_speaker(txt):
    """去掉「低声开口」「扬声开口」这类表演描述，只留人名。"""
    return re.sub(r"(\u4f4e\u58f0|\u626c\u58f0|\u9ad8\u58f0|\u6c89\u58f0|\u8f7b\u58f0)?(\u5f00\u53e3|\u8bf4\u9053|\u8bf4|\u9053)", "", txt).strip()


def speakers_in(prompt, names=None):
    """段表 prompt 里真正说话的角色（按出现顺序，去重）。

    ⚠️ 不能用「取冒号前最后 N 个字」这种粗暴办法：模型常写成
    「林渺低声开口：<d>…</d>」「老沙哑的嗓音开口：<d>…</d>」，
    抓出来的是描述词而不是人名 → 音色就绑错了人。
    所以优先**按已知角色名匹配**，匹配不到再退回启发式。
    """
    out = []
    for m in _DIALOG_TAG.finditer(prompt or ""):
        head = prompt[:m.start()]
        who = None
        if names:
            tail = head[-24:]
            best = None
            for n in names:
                idx = tail.rfind(n)
                if idx >= 0 and (best is None or idx > best[0]):
                    best = (idx, n)
            if best:
                who = best[1]
        if who is None:
            mm = _NAME_COLON.search(head)
            if mm:
                who = _clean_speaker(mm.group(1).strip())
        if who and who not in out:
            out.append(who)
    return out


def bind_voices(segment, table=None, max_refs=3, names=None):
    """给一段自动绑音色：说话人 -> 音色文件 -> <Audio N> 绑定。

    返回 (segment, 报告)。说话人超过 max_refs 时只绑前 max_refs 个（按台词字数优先），
    其余报告为「需拆镜头或用后期声音」。
    """
    table = table if table is not None else voice_table()
    if names is None:
        names = list(table.keys())
    prompt = segment.get("prompt", "") or ""
    speak = speakers_in(prompt, names)
    # 按台词字数排序（说话多的优先绑）
    weight = {}
    for m in _DIALOG_TAG.finditer(prompt):
        head = prompt[:m.start()]
        mm = _NAME_COLON.search(head)
        if mm:
            who = _clean_speaker(mm.group(1).strip())
            weight[who] = weight.get(who, 0) + len(m.group(1))
    ranked = sorted(speak, key=lambda x: -weight.get(x, 0))
    bound = [x for x in ranked if x in table][:max_refs]
    miss = [x for x in ranked if x not in table]
    dropped = [x for x in ranked if x in table and x not in bound]
    if not bound:
        return segment, {"ok": True, "bound": [], "miss": miss, "dropped": dropped,
                         "msg": "没有可绑的说话人"}
    # 写 <Audio N> 定义 + retention_analysis 的 reference 行
    lines = []
    for i, who in enumerate(bound):
        lines.append("<Audio %d> is the voice-timbre reference for %s." % (i + 1, who))
    defs = "\n".join(lines)
    prompt = prompt.replace("subject_definitions:\n",
                            "subject_definitions:\n" + defs + "\n", 1)
    ref_lines = []
    for i, who in enumerate(bound):
        ref_lines.append("<Audio %d>: reference - %s follows <Audio %d>'s voice timbre "
                         "and controlled delivery without copying the original signal."
                         % (i + 1, who, i + 1))
    marker = "\n\ndetailed_description:"
    if marker in prompt:
        prompt = prompt.replace(marker, "\n" + "\n".join(ref_lines) + marker, 1)
    else:
        prompt = prompt + "\n" + "\n".join(ref_lines)
    seg = dict(segment)
    seg["prompt"] = prompt
    seg["voice_refs"] = [table[w] for w in bound]
    seg["voice_modes"] = dict((table[w], "voice") for w in bound)
    msg = "绑了 %d 个音色: %s" % (len(bound), "、".join("%s→%s" % (w, table[w]) for w in bound))
    if dropped:
        msg += "；超参考预算未绑: " + "、".join(dropped) + "（需拆镜头或用后期声音）"
    if miss:
        msg += "；没有音色文件: " + "、".join(miss)
    return seg, {"ok": True, "bound": bound, "miss": miss, "dropped": dropped, "msg": msg}


def audit_voices(segments, table=None, names=None):
    """体检：每段实际说话的人 vs 挂上去的音色，对不上就报出来。"""
    table = table if table is not None else voice_table()
    if names is None:
        names = list(table.keys())
    bad = []
    for i, seg in enumerate(segments or []):
        prompt = seg.get("prompt", "") or ""
        speak = set(speakers_in(prompt, names))
        refs = seg.get("voice_refs") or []
        attached = set()
        for fn in refs:
            for who, f2 in table.items():
                if f2 == fn:
                    attached.add(who)
        no_voice = sorted(speak - attached)
        unused = sorted(attached - speak)
        if no_voice or unused:
            bad.append({"seg": i + 1, "speakers": sorted(speak),
                        "attached": sorted(attached),
                        "no_voice": no_voice, "unused": unused})
    return bad

def make_beat(chapter, duration, context="", asset_context="（参考资产库为空）", rebalance=True):
    """章节原文 -> 分镜任务书（带严格时间轴和台词预算）。

    2026-11-26：加了**场次时间重排**。原来 LLM 把每个场次钉死在固定秒数上，
    而场次里的台词常常装不下 → 分镜层怎么改都救不了（LLM 没有重分配的余地）。
    """
    user = chapter.strip()
    if context:
        user = context.strip() + NL2 + NL2 + user
    user = user + NL2 + NL2 + "目标总时长：%d秒" % duration + NL2 + BEAT_RULES
    user = user + NL2 + NL2 + "风格要求：" + GUOFENG_STYLE
    task = ai_call(sys_prompt("create_script", asset_context), user, max_tokens=6000)
    if rebalance:
        fixed, rep = rebalance_beats(task, total=duration)
        if rep.get("moved"):
            print("  场次时间重排:", rep["moved"])
        if not rep.get("ok"):
            print("  ⚠️ 场次时间装不下:", rep.get("msg"))
            for o in rep.get("over", []):
                print("     ", o)
        elif fixed != task:
            task = fixed
    return task



def beat_batches(task, batch_sec=75.0):
    """把场次表按累计时长切成批（每批约 batch_sec 秒），返回 [(场次块列表, 起始秒, 结束秒)]。"""
    head, blocks = beat_blocks(task)
    if not blocks:
        return [], []
    times = []
    for num, blk in blocks:
        m = _BEAT_TIME.search(blk)
        times.append((float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0))
    batches = []
    cur = []
    start = None
    for i, (num, blk) in enumerate(blocks):
        if start is None:
            start = times[i][0]
        cur.append((num, blk, times[i]))
        if times[i][1] - start >= batch_sec or i == len(blocks) - 1:
            batches.append((cur, start, times[i][1]))
            cur = []
            start = None
    return batches, times


def _extract_desc(block):
    """从一段分镜文本里抽出 integrated_multimodal_description 段。"""
    i = block.find("integrated_multimodal_description:")
    j = block.find("overall_soundscape:", i)
    if i < 0:
        # 没有标记就当整段都是描述
        return block.strip()
    if j < 0:
        j = len(block)
    return block[i + len("integrated_multimodal_description:"):j].strip()



def _at_sec(body):
    m = _SHOT_AT.search(body)
    return _sec(*m.groups()) if m else None


def retime_batch(desc, start, end):
    """把一批分镜的 At 时间戳重排：严格递增、覆盖 [start,end]、总时长守恒。

    为什么不信 LLM 的 At：实测它在同一批里会给出倒退的时间戳
    （导致负的镜头时长），守恒门禁直接判整段作废。自己算才稳。
    """
    span = max(0.001, end - start)
    parts = re.split(r"(?=\[Shot\s+\d+\])", desc)
    shots = [p for p in parts if p.lstrip().startswith("[Shot")]
    if len(shots) < 2:
        return desc
    starts = []
    cur = float(start)
    for p in shots:
        t = _at_sec(p)
        if t is None or t < cur or t > end:
            t = cur
        starts.append(t)
        cur = t
    durs = []
    for i in range(len(shots)):
        nxt = starts[i + 1] if i + 1 < len(shots) else float(end)
        durs.append(max(0.0, nxt - starts[i]))
    tot = sum(durs)
    if tot <= 0:
        durs = [span / len(shots)] * len(shots)
        tot = span
    # 台词镜不能短到念不完：每镜最小时长 = 字数/4（有富余的镜让出时间）
    durs = [d * span / tot for d in durs]
    mins = []
    for i, p in enumerate(shots):
        c = shot_chars(p)
        mins.append(c / 4.0 if c else 0.0)
    need = sum(mins)
    if need <= span:
        deficit = sum(max(0.0, mins[i] - durs[i]) for i in range(len(shots)))
        if deficit > 0:
            spare = sum(max(0.0, durs[i] - mins[i]) for i in range(len(shots)))
            take = min(deficit, spare)
            for i in range(len(shots)):
                if take <= 0:
                    break
                if durs[i] < mins[i]:
                    add = min(mins[i] - durs[i], take)
                    durs[i] += add
                    take -= add
                else:
                    give = min(durs[i] - mins[i], take)
                    durs[i] -= give
                    take -= give
    out = []
    t = float(start)
    for i, p in enumerate(shots):
        nb = p
        # 第一个 Shot 不写 At（官方格式要求），后续每个 Shot 必写且严格递增
        if i > 0:
            nb = _SHOT_AT.sub("At " + _fmt(t) + ",", nb, count=1)
            if _at_sec(nb) is None:
                nb = re.sub(r"(\[Shot\s+\d+\])", r"\1 At " + _fmt(t) + ",", nb, count=1)
        out.append(nb)
        t += durs[i]
    prefix = parts[0] if not parts[0].lstrip().startswith("[Shot") else ""
    return prefix + "".join(out)

def make_storyboard_batched(task, asset_context="（参考资产库为空）", batch_sec=75.0,
                            context="", verbose=True):
    """场次表 -> 官方 H3 分镜（按场次分批生成后拼接）。

    为什么必须分批：单次 LLM 输出有 token 上限（deepseek-chat 约 8K）。
    300 秒的戏按现在的详细度需要 15K+ token，一次生成会在 90 秒左右被截断，
    连 director_import_manifest 都写不出来 → 整段分镜作废。
    分批后每批 ~75 秒、输出 ~4~6K token，稳。
    """
    batches, _ = beat_batches(task, batch_sec)
    if not batches:
        return make_storyboard(task, asset_context=asset_context, context=context)
    if verbose:
        print("  分 %d 批生成（每批 ≤%.0f 秒）" % (len(batches), batch_sec))
    descs = []
    sounds = []
    for bi, (cur, start, end) in enumerate(batches):
        piece = "\n".join(blk for _n, blk, _t in cur)
        sub = task
        for _n, blk, _t in cur:
            sub = sub.replace(blk, "")
        sub = ("本批场次（绝对时间 %.3f–%.3f 秒）：\n%s\n\n"
               "只写这一批场次的分镜，Shot 的 At 时间戳用**绝对时间**（从 %.3f 秒起）。"
               % (start, end, piece, start))
        if verbose:
            print("    批 %d/%d：%.1f–%.1f 秒，%d 个场次" % (bi + 1, len(batches), start, end, len(cur)))
        raw = ai_call(sys_prompt("create_storyboard", asset_context),
                      sub + NL2 + NL2 + SHOT_RULES + NL2 + NL2 + SOUND_RULES
                      + NL2 + NL2 + "风格要求：" + GUOFENG_STYLE,
                      max_tokens=7000)
        descs.append(retime_batch(_extract_desc(raw), start, end))
        k = raw.find("overall_soundscape:")
        if k >= 0:
            e = raw.find("non_diegetic_music:", k)
            if e < 0:
                e = len(raw)
            sounds.append(raw[k + len("overall_soundscape:"):e].strip())
    # 拼描述，重新编号 Shot，绝对时间戳保持原样
    all_desc = "\n".join(descs)
    n = 0
    def renum(m):
        nonlocal n
        n += 1
        return "[Shot %d]" % n
    all_desc = re.sub(r"\[Shot\s+\d+\]", renum, all_desc)
    total = gm_total(task)
    sound = " ".join(s for s in sounds if s) or "环境声按各镜头描述。"
    board = ("integrated_multimodal_description:\n" + all_desc
             + "\n\noverall_soundscape:\n" + sound
             + "\n\nnon_diegetic_music:\nN/A"
             + "\n\ndirector_import_manifest:\nformat_version: 2\n"
             + "source_total_duration_seconds: %s\n" % total
             + "duration_policy: preserve")
    return board


def gm_total(task):
    """场次表声明的总时长。"""
    m = re.search(r"目标总时长：\s*(\d+(?:\.\d+)?)\s*秒", task)
    if m:
        return m.group(1)
    head, blocks = beat_blocks(task)
    if blocks:
        mm = _BEAT_TIME.search(blocks[-1][1])
        if mm:
            return mm.group(2)
    return "60"


def beats_demand(task, rate=3.5):
    """场次表里台词需要的总秒数（按 rate 字/秒）。"""
    head, blocks = beat_blocks(task)
    tot = 0.0
    for num, blk in blocks:
        tm = _BEAT_TIME.search(blk)
        d = (float(tm.group(2)) - float(tm.group(1))) if tm else 0.0
        tot += max(d, beat_dialogue_chars(blk) / rate if beat_dialogue_chars(blk) else 0.0)
    return tot


def fit_beats_to_budget(task, rate=3.5, min_total=None):
    """台词装不下时，自动把总时长扩到刚好装得下（按原比例摊），并改写「目标总时长」。

    为什么是加长而不是砍台词：砍台词会伤剧情和节奏；短剧本来就常在
    「台词刚好的密度」上取平衡。程序化扩容是保内容的做法。
    """
    head, blocks = beat_blocks(task)
    if not blocks:
        return task, {"ok": False, "msg": "没解析到场次"}
    demand = beats_demand(task, rate)
    m = re.search(r"目标总时长：\s*(\d+(?:\.\d+)?)\s*秒", task)
    cur = float(m.group(1)) if m else sum(
        (float(_BEAT_TIME.search(b[1]).group(2)) if _BEAT_TIME.search(b[1]) else 0)
        for b in blocks)
    need = max(demand, cur)
    if min_total:
        need = max(need, min_total)
    if need <= cur + 1e-6:
        return task, {"ok": True, "total": cur, "demand": round(demand, 1),
                     "msg": "台词装得下（需求 %.1f 秒 / 目标 %.1f 秒）" % (demand, cur)}
    fixed, rep = rebalance_beats(task, total=need)
    fixed = re.sub(r"目标总时长：\s*\d+(?:\.\d+)?\s*秒",
                   "目标总时长：%d秒" % int(round(need)), fixed)
    return fixed, {"ok": True, "total": round(need, 1), "demand": round(demand, 1),
                   "extended_from": cur,
                   "msg": "台词需要 %.1f 秒 → 整集自动加长到 %.1f 秒（不砍台词）"
                           % (demand, need)}

def parse_segments(board, original_input="", seed=0):
    """官方分镜 -> 导演台 segments_json 数组（复用插件解析器）。"""
    proc = subprocess.run(
        ["node", os.path.join(HERE, "h3_segments.mjs")],
        input=json.dumps({"storyboard": board, "original_input": original_input,
                          "seed": seed}, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("分镜解析失败: " + proc.stderr[:500])
    res = json.loads(proc.stdout)
    if not res.get("ok"):
        raise RuntimeError("分镜不合法: " + str(res.get("error")))
    return res


def build_prompt(segments, duration=None, global_prompt=GUOFENG_STYLE,
                  wf_path=DIRECTOR_WF):
    """用 wf2api 把导演台工作流转成 API prompt，并填入分段。"""
    sys.path.insert(0, HERE)
    import wf2api
    oi_path = os.path.join(ROOT, "_oi_now.json")
    if os.path.exists(oi_path):
        oi = json.load(io.open(oi_path, encoding="utf-8"))
    else:
        oi = _get("/object_info")
        io.open(oi_path, "w", encoding="utf-8").write(
            json.dumps(oi, ensure_ascii=False))
    wf = json.load(io.open(wf_path, encoding="utf-8"))
    prompt, notes = wf2api.convert(wf, oi)
    for n in notes:
        print("  ~", n)
    studio = prompt.get(STUDIO_NODE)
    if studio is None:
        raise RuntimeError("导演台工作流里找不到 H3DirectorStudio 节点")
    studio["inputs"]["segments_json"] = json.dumps(segments, ensure_ascii=False)
    if duration:
        studio["inputs"]["时长秒"] = duration
    studio["inputs"]["global_prompt"] = global_prompt
    return prompt


def queue_video(prompt, wait=True, poll=15):
    """提交 API prompt 出片。"""
    res = _post("/prompt", {"prompt": prompt})
    pid = res["prompt_id"]
    print("已提交 prompt_id:", pid)
    if not wait:
        return pid
    while True:
        try:
            hist = _get("/history/" + pid)
        except Exception:
            time.sleep(poll)
            continue
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status") or {}
            print("状态:", status.get("status_str"))
            for msg in (status.get("messages") or [])[-8:]:
                print("  ", str(msg)[:400])
            for oid, val in (entry.get("outputs") or {}).items():
                for vid in (val.get("video") or []):
                    print("成片:", vid.get("filename"), "|", vid.get("subfolder"))
            return pid
        time.sleep(poll)


def _read(path):
    return io.open(path, encoding="utf-8").read()


def _write(path, text):
    io.open(path, "w", encoding="utf-8").write(text)
    print("已写出:", path)


def _args(rest):
    src = None
    out_path = None
    duration = 0
    dry = False
    context_path = None
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "-o" and i + 1 < len(rest):
            out_path = rest[i + 1]; i += 2; continue
        if a == "--duration" and i + 1 < len(rest):
            duration = int(float(rest[i + 1])); i += 2; continue
        if a == "--dry":
            dry = True; i += 1; continue
        if a == "--context" and i + 1 < len(rest):
            context_path = rest[i + 1]; i += 2; continue
        src = a; i += 1
    return src, out_path, duration, dry, context_path


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    src, out_path, duration, dry, context_path = _args(args[1:])
    if not src:
        print("缺少输入文件")
        return 1
    context = _read(context_path) if context_path else ""

    if cmd == "script":
        text = make_script(_read(src), duration, context=context)
        _write(out_path or "script.txt", text)
    elif cmd == "storyboard":
        text = make_storyboard(_read(src), context=context)
        _write(out_path or "storyboard.txt", text)
    elif cmd == "beat":
        text = make_beat(_read(src), duration or 60, context=context)
        _write(out_path or "分镜任务书.txt", text)
    elif cmd == "segments":
        res = parse_segments(_read(src), _read(src), seed=duration)
        print("段数:", len(res["segments"]), "| 总时长:", res.get("source_duration"))
        _write(out_path or "segments.json",
               json.dumps(res["segments"], ensure_ascii=False, indent=1))
    elif cmd == "video":
        segments = json.loads(_read(src))
        if not duration:
            duration = sum(float(s.get("duration") or 0) for s in segments)
        prompt = build_prompt(segments, duration or None)
        if dry:
            print(json.dumps(prompt[STUDIO_NODE]["inputs"], ensure_ascii=False)[:900])
            return 0
        queue_video(prompt)
    elif cmd == "all":
        novel = _read(src)
        print("[1/4] AI剧情 ...")
        script = make_script(novel, duration, context=context)
        print("[2/4] AI分镜 ...")
        board = make_storyboard(script, context=context)
        print("[3/4] 解析分段 ...")
        res = parse_segments(board, script)
        segments = res["segments"]
        print("      段数:", len(segments), "| 总时长:", res.get("source_duration"))
        io.open("storyboard.txt", "w", encoding="utf-8").write(board)
        io.open("script.txt", "w", encoding="utf-8").write(script)
        io.open("segments.json", "w", encoding="utf-8").write(
            json.dumps(segments, ensure_ascii=False, indent=1))
        print("[4/4] 出片 ...")
        prompt = build_prompt(segments, duration or res.get("source_duration"))
        if dry:
            print(json.dumps(prompt[STUDIO_NODE]["inputs"], ensure_ascii=False)[:900])
            return 0
        queue_video(prompt)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
