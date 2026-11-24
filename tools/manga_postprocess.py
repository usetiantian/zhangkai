"""把官方 Base 分镜升级成导演台 Ref2VA 格式，并绑定角色定妆参考图。

做三件事：
  1. 每个 Shot 前面补上风格句（AI 不会每镜重复风格，必须确定性地补）
  2. 把 integrated_multimodal_description 改写成完整的 Ref2VA 六字段，
     显式写 <Subject N> is the character XXX defined by <Picture N>
  3. 按每段出场的角色，给段填 refs（角色定妆图）

用法:
  python tools/manga_postprocess.py <segments.json> [-o out.json]
"""
import io
import json
import os
import re
import sys

STYLE = ("国产玄幻动漫风格，高饱和度厚涂上色，精细锐利描边，深邃明暗对比与体积光，"
         "人物边缘轮廓光，高饱和玄幻配色，画面带灵气粒子与法术光效；")

# 角色顺序固定（决定 <Picture N> 编号）；图片取自 00_素材/当前造型.json
ROLE_ORDER = ["林渺", "苏禾", "王天霸", "林守田", "林小雨"]
CUR_MAP = "manga/渺渺仙途/00_素材/当前造型.json"
VOICE_MAP = "manga/渺渺仙途/00_素材/音色/音色表.json"


def load_chars():
    out = []
    cur = {}
    if os.path.exists(CUR_MAP):
        cur = json.load(io.open(CUR_MAP, encoding="utf-8"))
    for name in ROLE_ORDER:
        img = cur.get(name)
        if img:
            out.append((name, img))
    return out


def load_voices():
    if os.path.exists(VOICE_MAP):
        return json.load(io.open(VOICE_MAP, encoding="utf-8"))
    return {}


def main_speaker(text, chars):
    """段内台词最多的人 = 主说话人，用他的克隆音色。

    AI 写台词有多种格式：「林渺：<d>…」「林渺低声开口。<d>…」，
    所以不能只匹配固定前缀，要看每个 <d> 前面最近出现的是哪个角色名。
    """
    counts = {}
    for m in re.finditer(r"<d>", text):
        head = text[max(0, m.start() - 40):m.start()]
        hit = None
        for name, _f in chars:
            pos = head.rfind(name)
            if pos >= 0 and (hit is None or pos > head.rfind(hit)):
                hit = name
        if hit:
            counts[hit] = counts.get(hit, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]

FIELD_RE = re.compile(
    r"(?m)^(integrated_multimodal_description|overall_soundscape|non_diegetic_music|"
    r"subject_definitions|summary|retention_analysis|detailed_description)\s*[:：]\s*$")


def split_fields(text):
    marks = list(FIELD_RE.finditer(text))
    if not marks:
        return {}, text.strip()
    fields = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        fields[m.group(1).lower()] = text[m.end():end].strip()
    return fields, text[:marks[0].start()].strip()


# 角色速写：LLM 一定会把外观细节概括掉，必须确定性地注入到每个镜头里
CHAR_TAGS = {
    "林渺": "（黑色长发束成高马尾，深青色布发带扎紧，鬓边碎发，灰蓝色交领束袖劲装，"
            "深褐色束腰，深灰绑腿黑布靴，腰间挂拇指大的青色小葫芦）",
    "苏禾": "（黑色长发盘成圆髻插一支银簪，白色交领罗裙，青色披帛搭在臂弯，腰间羊脂玉佩）",
    "王天霸": "（黑色高冠束发，暗纹锦缎长袍，满脸横肉，肩膀宽厚比旁人高半头）",
    "林守田": "（花白头发用灰色布巾束在脑后，额头眼角皱纹深刻，背有些佝偻，灰布短衫）",
    "林小雨": "（双丫髻扎红头绳，红碎花布衫，个头只到哥哥肩膀）",
}


INNER_RE = re.compile(r"<d>\[Chinese\]\s*(（内心独白）[^<]*?)\s*</d>")
NARR_RE = re.compile(r"<d>\[Chinese\]\s*(旁白（画面无人开口）[：:]?[^<]*?)\s*</d>")
# AI 也常把标记写在标签前面：「林渺内心独白。<d>[Chinese]xxx</d>」
INNER_PRE_RE = re.compile(
    r"((?:^|[。；;\s])(?:[一-龥]{1,4})?内心独白[。：:，,]?)\s*<d>\[Chinese\]([^<]*?)</d>")
NARR_PRE_RE = re.compile(
    r"((?:^|[。；;\s])旁白(?:（画面无人开口）)?[：:]?)\s*<d>\[Chinese\]([^<]*?)</d>")


def strip_inner_voice(text):
    """内心独白/旁白不能进 <d>（进了角色就会张嘴把心里话说出来）。

    AI 常常写成「角色名：（内心独白）xxx」，再被转成 <d>。这里确定性地摘掉 <d>，
    保留成镜头描述里的闭口内心戏。
    """
    text = INNER_RE.sub(lambda m: m.group(1) + "，人物闭口不言，只用眼神与表情演出", text)
    text = NARR_RE.sub(lambda m: m.group(1) + "，画面中无人开口", text)
    text = INNER_PRE_RE.sub(
        lambda m: m.group(1) + m.group(2) + "（人物闭口不言，只用眼神与表情演出）", text)
    text = NARR_PRE_RE.sub(
        lambda m: m.group(1) + m.group(2) + "（画面中无人开口）", text)
    return text


def add_style(text):
    """给每个 [Shot N] 行前面补风格句，并在角色首次出现处注入角色速写。"""
    lines = text.splitlines()
    out = []
    for line in lines:
        if re.match(r"^\s*\[Shot\s+\d+\]", line):
            body = line.strip()
            for name, tag in CHAR_TAGS.items():
                if name in body:
                    body = body.replace(name, name + tag, 1)
            out.append(STYLE + body)
        else:
            out.append(line)
    return "\n".join(out)


def build_ref2va(prompt, characters, episode=""):
    fields, prefix = split_fields(prompt)
    detailed = fields.get("detailed_description") or fields.get("integrated_multimodal_description") or ""
    detailed = add_style(detailed)
    detailed = strip_inner_voice(detailed)
    soundscape = fields.get("overall_soundscape") or "自然环境声与动作声，与镜头描述同步。"
    music = fields.get("non_diegetic_music") or "N/A"

    defs = []
    retains = []
    for index, name in enumerate(characters, 1):
        defs.append("<Subject %d> is the character %s defined by <Picture %d>." % (index, name, index))
        retains.append(
            "<Subject %d>:partially_preserved - 保持 <Picture %d> 中 %s 的面部特征、发型、"
            "体型、身高比例与服装配饰完全一致，不要改变人物身份与造型；"
            "场景、动作与运镜按下方镜头描述执行。" % (index, index, name))
    if not defs:
        defs = ["N/A"]
        retains = ["N/A"]

    summary = ("《渺渺仙途》古装玄幻短剧%s的一段。画面为国产玄幻动漫风格，"
               "人物与场景按下方镜头描述执行。" % (("（" + episode + "）") if episode else ""))
    parts = [
        "subject_definitions:\n" + "\n".join(defs),
        "summary:\n" + summary,
        "retention_analysis:\n" + "\n".join(retains),
        "detailed_description:\n" + detailed,
        "overall_soundscape:\n" + soundscape,
        "non_diegetic_music:\n" + music,
    ]
    return "\n\n".join(parts)


def main():
    args = sys.argv[1:]
    src = args[0]
    out_path = args[args.index("-o") + 1] if "-o" in args else None
    episode = args[args.index("--ep") + 1] if "--ep" in args else ""
    chars = load_chars()
    voices = load_voices()
    segs = json.load(io.open(src, encoding="utf-8"))
    for seg in segs:
        text = seg.get("prompt") or ""
        # 只按镜头正文判断出场角色；overall_soundscape 里提到的人不算出场
        fields, _prefix = split_fields(text)
        body = fields.get("detailed_description") or fields.get("integrated_multimodal_description") or text
        present = [name for name, _f in chars if name in body]
        refs = []
        for name in present:
            for n, f in chars:
                if n == name:
                    refs.append(f)
        seg["prompt"] = build_ref2va(text, present, episode)
        seg["refs"] = refs
        seg.pop("video_refs", None)
        if voices:
            speaker = main_speaker(body, chars)
            vfile = voices.get(speaker) if speaker else None
            if vfile:
                seg["voice_refs"] = [vfile]
                seg["voice_modes"] = {vfile: "voice"}
        print("段: 角色 %s -> refs %s | 音色 %s" % (
            "、".join(present) or "无", refs, seg.get("voice_refs")))
    dest = out_path or src
    io.open(dest, "w", encoding="utf-8").write(json.dumps(segs, ensure_ascii=False, indent=1))
    print("已写出:", dest)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
