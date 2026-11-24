# -*- coding: utf-8 -*-
"""拼接 H3 导演台各段 MP4 -> 成片 (带音轨, 24fps)"""
import os, glob, subprocess, sys
FF = r"D:\ffmpeg\bin\ffmpeg.exe"
d = r"D:\ComfyUI_windows_portable\ComfyUI\output\video\h3director\wjcs_xueji_v1"
out = r"C:\Users\87999\claude-workspace\问剑长生_血祭古剑_EP01.mp4"
files = sorted(glob.glob(os.path.join(d, "漫剧_seg*_一次采样.mp4")))
print("found %d segment(s):" % len(files))
for f in files: print("  ", os.path.basename(f))
if not files:
    sys.exit(1)
lst = os.path.join(d, "_concat_list.txt")
with open(lst, "w", encoding="utf-8") as fh:
    for f in files:
        fh.write("file '%s'\n" % f.replace("\\", "/").replace("'", "'\''"))
cmd = [FF, "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", lst,
       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
       "-r", "24", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
print(" ".join(cmd))
subprocess.run(cmd, check=True)
print("OUTPUT:", out, os.path.getsize(out), "bytes")
