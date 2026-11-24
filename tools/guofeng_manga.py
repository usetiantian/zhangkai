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


def make_storyboard(script, asset_context="（参考资产库为空）", context=""):
    """剧本 -> 官方 H3 分镜。"""
    user = script.strip()
    if context:
        user = context.strip() + NL2 + NL2 + user
    user = user + NL2 + NL2 + "风格要求：" + GUOFENG_STYLE
    return ai_call(sys_prompt("create_storyboard", asset_context), user)


BEAT_RULES = """
【输出格式要求 — 严格照做，不要任何解释、小标题或 Markdown】
1. 第一行必须且只能写：目标总时长：X秒（X 就是给定的目标总时长）
2. 之后每个场次严格按下面五行写，场次之间空一行：
场次N
起始秒–结束秒
场景与时间：…
出场人物：…
△动作描述…
角色名：台词
3. 所有场次的时间首尾相接，第一个从 0.000 秒开始，最后一个结束正好等于 X 秒。
4. 每句台词的汉字数（含标点）必须不超过该场次秒数乘 4。超了就把台词改短，
   或者把这一场的时间拉长。台词短促、克制、有信息量，不要长篇大论。
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


def make_beat(chapter, duration, context="", asset_context="（参考资产库为空）"):
    """章节原文 -> 分镜任务书（带严格时间轴和台词预算）。"""
    user = chapter.strip()
    if context:
        user = context.strip() + NL2 + NL2 + user
    user = user + NL2 + NL2 + "目标总时长：%d秒" % duration + NL2 + BEAT_RULES
    user = user + NL2 + NL2 + "风格要求：" + GUOFENG_STYLE
    return ai_call(sys_prompt("create_script", asset_context), user, max_tokens=6000)


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
