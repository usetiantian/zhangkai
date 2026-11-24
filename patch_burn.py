# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "postproduce.py"
t = open(F, encoding="utf-8").read()
old = t[t.index("def concat_and_burn("):]
new = '''def concat_and_burn(shot_videos, master_wav, ass_path, out_path, crf=18):
    """视频流拼接 + 挂成品音轨 + 烧 ASS 字幕。

    Windows 下 ass filter 的路径转义很脆弱（冒号 + 中文目录名）。
    做法：把字幕复制到纯 ASCII 临时目录，用相对文件名引用，cwd 指向该目录。
    """
    import shutil
    lst = os.path.join(tempfile.gettempdir(), "_concat_%d.txt" % os.getpid())
    with open(lst, "w", encoding="utf-8") as fh:
        for v in shot_videos:
            fh.write("file '%s'\n" % v.replace("\\\\", "/"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmpd = tempfile.mkdtemp(prefix="epburn_")
    shutil.copy2(ass_path, os.path.join(tmpd, "subs.ass"))
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", lst,
           "-i", master_wav,
           "-map", "0:v:0", "-map", "1:a:0", "-vf", "ass=subs.ass",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, cwd=tmpd)
    return out_path
'''
t = t.replace(old, new)
open(F, "w", encoding="utf-8").write(t)
print("postproduce.concat_and_burn rewritten")
