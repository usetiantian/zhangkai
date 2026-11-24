"""把官方分镜的时间轴确定性地缩放到目标总时长。

AI 经常把 75 秒写成 86~116 秒（Shot 拆太碎）。内容本身没问题，
所以这里不动内容，只按比例缩放所有 At 时间戳，并重写 manifest。

用法: python tools/manga_retime.py <分镜.txt> [--duration 75] [-o out.txt]
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CLOCK = re.compile(r"At\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
MANIFEST = re.compile(r"(source_total_duration_seconds|target_total_duration_seconds|源总时长秒|目标总时长秒)"
                      r"\s*[:：=]\s*([\d.]+)")
SHOT = re.compile(r"(?m)^\[Shot\s+\d+\]")


def to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def clock(seconds):
    total = int(round(seconds * 1000))
    h = total // 3600000
    total %= 3600000
    m = total // 60000
    total %= 60000
    s = total // 1000
    ms = total % 1000
    return "%02d:%02d:%02d.%03d" % (h, m, s, ms)


def main():
    args = sys.argv[1:]
    src = args[0]
    target = 75.0
    out = None
    for i, a in enumerate(args):
        if a == "--duration" and i + 1 < len(args):
            target = float(args[i + 1])
        elif a == "-o" and i + 1 < len(args):
            out = args[i + 1]
    text = io.open(src, encoding="utf-8").read()

    stamps = [(m.start(), to_seconds(*m.groups())) for m in CLOCK.finditer(text)]
    if not stamps:
        print("没有 At 时间戳，无法重定时")
        return 1
    span = None
    # 让插件自己算"导入时长"（最后一个 Shot 的真实结束时间），别自己猜
    probe = subprocess.run(["node", os.path.join(HERE, "h3_segments.mjs")],
                           input=json.dumps({"storyboard": text, "mode": "duration"},
                                            ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    if probe.returncode == 0:
        try:
            info = json.loads(probe.stdout)
            if info.get("imported_duration"):
                span = float(info["imported_duration"])
        except Exception:
            span = None
    if not span:
        m = MANIFEST.search(text)
        span = float(m.group(2)) if m else stamps[-1][1] + 4.0
    if span <= 0:
        print("总跨度异常:", span)
        return 1
    ratio = target / span
    print("原跨度 %.3f 秒 -> 目标 %.3f 秒，比例 %.4f（%d 个时间戳）"
          % (span, target, ratio, len(stamps)))

    pieces = []
    last = 0
    for pos, val in stamps:
        pieces.append(text[last:pos])
        pieces.append("At " + clock(val * ratio))
        last = pos + len(CLOCK.search(text[pos:]).group(0))
    pieces.append(text[last:])
    text = "".join(pieces)

    if MANIFEST.search(text):
        text = MANIFEST.sub(lambda mm: mm.group(1) + ": " + ("%g" % target), text, count=1)
    else:
        text = text.rstrip() + ("\n\ndirector_import_manifest:\nformat_version: 2\n"
                                "source_total_duration_seconds: %g\nduration_policy: preserve\n" % target)
    dest = out or src
    io.open(dest, "w", encoding="utf-8").write(text)
    print("已重定时 ->", dest)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
