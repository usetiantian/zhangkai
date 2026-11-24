# -*- coding: utf-8 -*-
"""按分镜顺序拼装 EP01（显式文件列表，支持替换某一镜）"""
import os, subprocess, sys, glob
FF=r"D:\ffmpeg\bin\ffmpeg.exe"
BASE=r"D:\ComfyUI_windows_portable\ComfyUI\output\video\h3director"
OUT=r"C:\Users\87999\claude-workspace\问剑长生_血祭古剑_EP01.mp4"
# (工程目录, 段号)
ORDER=[("wjcs_xueji_v1",1),("wjcs_xueji_v2",1),("wjcs_xueji_v1",3),("wjcs_xueji_v1",4)]
def pick(proj,seg,suffix):
    d=os.path.join(BASE,proj)
    c=glob.glob(os.path.join(d,"漫剧_seg%d_*%s*.mp4"%(seg,suffix)))
    return sorted(c)[-1] if c else None
files=[]; missing=[]
for i,(proj,seg) in enumerate(ORDER,1):
    suffix = sys.argv[1] if len(sys.argv)>1 else "一次采样"
    f=pick(proj,seg,suffix)
    if not f: missing.append((proj,seg,suffix)); continue
    files.append(f); print("镜%d <- %s"%(i,os.path.basename(f)))
if missing: print("MISSING:",missing); sys.exit(1)
lst=os.path.join(BASE,"_ep01_list.txt")
with open(lst,"w",encoding="utf-8") as fh:
    for f in files: fh.write("file '%s'\n"%f.replace("\\","/"))
cmd=[FF,"-hide_banner","-y","-f","concat","-safe","0","-i",lst,"-c:v","libx264",
     "-preset","medium","-crf","18","-pix_fmt","yuv420p","-r","24",
     "-c:a","aac","-b:a","192k","-movflags","+faststart",OUT]
subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print("OUTPUT:",OUT,os.path.getsize(OUT),"bytes")
