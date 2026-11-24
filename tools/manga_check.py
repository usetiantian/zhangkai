"""校验分镜任务书：时间轴连续性 + 台词语速预算。

用法: python tools/manga_check.py <分镜任务书.txt>
"""
import io
import re
import sys

MAX_CHARS_PER_SEC = 4.0      # H3 正常语速上限（字/秒，含标点）
SCENE_RE = re.compile(r"^场次\s*(\d+)\s*$")
TIME_RE = re.compile(r"^([\d.]+)\s*[–\-~]\s*([\d.]+)\s*秒\s*$")
LINE_RE = re.compile(r"^([^:：△]{1,12})[:：](.+)$")


def parse(path):
    text = io.open(path, encoding="utf-8").read()
    scenes = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = SCENE_RE.match(line)
        if m:
            cur = {"no": int(m.group(1)), "lines": []}
            scenes.append(cur)
            continue
        if cur is None:
            continue
        cur["lines"].append(line)
    out = []
    for sc in scenes:
        item = {"no": sc["no"], "start": None, "end": None, "dialogue": [], "action": ""}
        for line in sc["lines"]:
            tm = TIME_RE.match(line)
            if tm and item["start"] is None:
                item["start"] = float(tm.group(1))
                item["end"] = float(tm.group(2))
                continue
            if line.startswith("△"):
                item["action"] += line[1:]
                continue
            dm = LINE_RE.match(line)
            if dm and not line.startswith("场景与时间") and not line.startswith("出场人物"):
                name = dm.group(1).strip()
                say = dm.group(2).strip()
                if name in ("目标总时长", "创作要求", "风格要求"):
                    continue
                item["dialogue"].append((name, say))
        out.append(item)
    return out


def count_chars(s):
    return len([c for c in s if not c.isspace()])


def main():
    path = sys.argv[1]
    scenes = parse(path)
    if not scenes:
        print("没解析出场次")
        return 1
    errs = []
    warns = []
    total = scenes[-1]["end"] or 0
    prev_end = 0.0
    for sc in scenes:
        if sc["start"] is None:
            errs.append("场次%d 缺时间行" % sc["no"])
            continue
        if abs(sc["start"] - prev_end) > 0.01:
            errs.append("场次%d 起点 %.3f 与上一场结束 %.3f 不连续" % (sc["no"], sc["start"], prev_end))
        dur = sc["end"] - sc["start"]
        if dur <= 0:
            errs.append("场次%d 时长非正" % sc["no"])
        budget = dur * MAX_CHARS_PER_SEC
        for name, say in sc["dialogue"]:
            n = count_chars(say)
            if n > budget:
                errs.append("场次%d 台词超速: '%s' %d字 / 本场 %.1fs (上限 %.1f字)"
                            % (sc["no"], say[:18], n, dur, budget))
            elif n > budget * 0.9:
                warns.append("场次%d 台词接近上限: '%s' %d字 / %.1fs" % (sc["no"], say[:18], n, dur))
        prev_end = sc["end"]
    print("场次数:", len(scenes), "| 总时长: %.3f 秒" % total)
    for sc in scenes:
        dur = (sc["end"] or 0) - (sc["start"] or 0)
        print("  场次%d  %6.2f-%6.2f (%4.1fs) 台词%d句"
              % (sc["no"], sc["start"] or 0, sc["end"] or 0, dur, len(sc["dialogue"])))
    # 内心独白/旁白不能被当成角色台词（后处理会自动从 <d> 里摘出，这里只提醒）
    for sc in scenes:
        for name, say in sc["dialogue"]:
            if "内心独白" in say or "旁白" in say:
                warns.append("场次%d '%s' 是内心独白/旁白，后处理会自动从 <d> 里摘出，"
                             "人物保持闭口" % (sc["no"], say[:16]))
    for w in warns:
        print("  ~", w)
    for e in errs:
        print("  !", e)
    print("\n结论:", "通过" if not errs else "有 %d 处问题" % len(errs))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
