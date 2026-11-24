"""确保官方分镜带合法的 director_import_manifest（AI 经常漏写）。

用法: python tools/manga_manifest.py <分镜.txt> [--duration 75] [-o out.txt]
"""
import io
import re
import sys


def main():
    args = sys.argv[1:]
    src = args[0]
    duration = 75.0
    out = None
    for i, a in enumerate(args):
        if a == "--duration" and i + 1 < len(args):
            duration = float(args[i + 1])
        elif a == "-o" and i + 1 < len(args):
            out = args[i + 1]
    text = io.open(src, encoding="utf-8").read()
    if re.search(r"(?m)^\s*director_import_manifest\s*[:：]", text):
        m = re.search(r"source_total_duration_seconds\s*[:：=]\s*([\d.]+)", text)
        if m:
            print("manifest 已存在，无需修补")
            return 0
    # 从剧本首行找目标总时长
    m = re.search(r"目标总时长\s*[:：]\s*([\d.]+)\s*秒", text)
    if m:
        duration = float(m.group(1))
    text = text.rstrip() + (
        "\n\ndirector_import_manifest:\n"
        "format_version: 2\n"
        "source_total_duration_seconds: %s\n"
        "duration_policy: preserve\n" % duration)
    dest = out or src
    io.open(dest, "w", encoding="utf-8").write(text)
    print("已补 director_import_manifest，总时长", duration, "->", dest)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
