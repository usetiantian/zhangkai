"""把导演台产出的分段 MP4 合并成整集。

自动挑每个段号「最新版本」的文件（导演台单段重抽会生成新的编号文件）。
用法: python tools/manga_merge.py <project_id> [段数] [输出目录]
"""
import io
import os
import re
import subprocess
import sys
import time

COMFY_ROOT = os.environ.get("COMFY_ROOT", "D:/ComfyUI_windows_portable/ComfyUI")
# 注意：python_embeded 与 ComfyUI 目录同级，不在 ComfyUI 里面
FFMPEG = os.environ.get(
    "FFMPEG",
    os.path.join(os.path.dirname(COMFY_ROOT), "python_embeded", "Lib", "site-packages",
                 "imageio_ffmpeg", "binaries", "ffmpeg-win-x86_64-v7.1.exe"))
SEG_RE = re.compile(r"_seg(\d+)_(\d+)_一次采样\.mp4$")


def pick_latest(vdir, count):
    """每个段号取 mtime 最新的一个版本。"""
    best = {}
    for name in os.listdir(vdir):
        if not name.endswith("_一次采样.mp4"):
            continue
        m = SEG_RE.search(name)
        if not m:
            continue
        seg = int(m.group(1))
        path = os.path.join(vdir, name)
        mtime = os.path.getmtime(path)
        if seg not in best or mtime > best[seg][1]:
            best[seg] = (path, mtime)
    return [best[s][0] for s in sorted(best) if s <= count]


def main():
    project_id = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "."
    vdir = os.path.join(COMFY_ROOT, "output", "video", "h3director", project_id)
    files = pick_latest(vdir, count)
    if not files:
        print("在", vdir, "没找到分段文件")
        return 1
    print("合并 %d 段:" % len(files))
    for f in files:
        print("   ", os.path.basename(f))
    stamp = time.strftime("%m%d_%H%M%S")
    lst = os.path.join(out_dir, "_concat_%s.txt" % stamp)
    io.open(lst, "w", encoding="utf-8").write(
        "".join("file '%s'\n" % p.replace("\\", "/") for p in files))
    dst = os.path.join(out_dir, "整集_%s.mp4" % stamp)
    ffmpeg = os.path.normpath(FFMPEG)
    r = subprocess.run([ffmpeg, "-n", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", dst],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("ffmpeg 失败:", r.stderr[-500:])
        return 1
    print("整集 ->", dst, "|", os.path.getsize(dst) // 1024, "KB")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
