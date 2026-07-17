# -*- coding: utf-8 -*-
"""B站视频 -> 多模态种子 -> WorldModel训练 完整管线
搜索: B站热门榜(免登录) / 指定BV号
下载: yt-dlp (360p, 免cookie)
拆解: ffmpeg (音频+关键帧)
编码: Text/Image/Audio/Video → WorldModel
训练: SelfPlay消化新知识
"""
import sys,io,os,re,json,time,subprocess,tempfile,shutil,urllib.request
from pathlib import Path
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
NEXUS_HOME=Path(__file__).parent.parent
VIDEO_CACHE=NEXUS_HOME/"data"/"videos"
VIDEO_CACHE.mkdir(parents=True,exist_ok=True)

def get_wm():
    from nexus_agent.world_model import get_world_model
    return get_world_model()

def search_hot(limit:int=10)->list:
    """B站热门榜 (免登录)."""
    url="https://api.bilibili.com/x/web-interface/popular?ps=50"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.bilibili.com"})
    try:
        with urllib.request.urlopen(req,timeout=10)as resp:
            data=json.loads(resp.read().decode())
        items=data.get("data",{}).get("list",[])
        return[{"bvid":i.get("bvid",""),"title":i.get("title",""),"author":i.get("owner",{}).get("name",""),
                "duration":i.get("duration",0)}for i in items[:limit]]
    except Exception as e:
        print(f"[B站热门] err: {e}")
        return[]

def search_keyword(keyword:str,limit:int=5)->list:
    """搜索B站 (使用yt-dlp内置搜索)."""
    try:
        result=subprocess.run(["yt-dlp",f"bilisearch{limit}:{keyword}",
            "--flat-playlist","--dump-json","--no-warnings","--no-check-certificate"],
            capture_output=True,timeout=30,encoding="utf-8",errors="replace")
        videos=[]
        for line in result.stdout.strip().split("\n"):
            if not line.strip():continue
            try:
                d=json.loads(line)
                vid=d.get("id","")
                if vid.startswith("BV"):
                    videos.append({"bvid":vid,"title":d.get("title",""),"duration":d.get("duration",0)})
            except:pass
        return videos[:limit]
    except Exception as e:
        print(f"[搜索] {keyword}: {e}")
        return[]

def download(bvid:str,output_dir:str=None,max_mb:int=80)->str|None:
    """下载B站视频 (360p, 免cookie)."""
    dest=output_dir or str(VIDEO_CACHE)
    url=f"https://www.bilibili.com/video/{bvid}"
    out=f"{dest}/{bvid}.mp4"
    if os.path.exists(out) and os.path.getsize(out)>10000:return out
    try:
        subprocess.run(["yt-dlp",url,"-o",out,"-f","bv*[height<=360]+ba*",
            "--no-warnings","--no-check-certificate"],
            capture_output=True,timeout=90,encoding="utf-8",errors="replace")
        if os.path.exists(out) and os.path.getsize(out)>10000:
            return out
    except:pass
    return None

def extract(bvid:str,video_path:str,title:str)->dict:
    """拆解视频 → 音频+关键帧. 返回种子路径字典."""
    wd=Path(video_path).parent
    seeds={"bvid":bvid,"title":title,"text":title,"audio":None,"frames":[],"video":video_path}
    ap=str(wd/f"{bvid}_audio.wav")
    try:
        subprocess.run(["ffmpeg","-y","-i",video_path,"-vn","-acodec","pcm_s16le",
            "-ar","16000","-ac","1","-t","120",ap],capture_output=True,timeout=30)
        if os.path.exists(ap) and os.path.getsize(ap)>1000:seeds["audio"]=ap
    except:pass
    try:
        fp=str(wd/f"{bvid}_f_%02d.png")
        subprocess.run(["ffmpeg","-y","-i",video_path,"-vf","fps=1/10",
            "-vframes","6",fp],capture_output=True,timeout=30)
        for i in range(1,7):
            p=str(wd/f"{bvid}_f_{i:02d}.png")
            if os.path.exists(p) and os.path.getsize(p)>100:seeds["frames"].append(p)
    except:pass
    return seeds

def encode(seeds:dict)->dict:
    """编码所有种子→WorldModel."""
    wm=get_wm()
    r={"bvid":seeds["bvid"],"count":0}
    wm.observe("text",seeds["text"],label=f"bili:{seeds['bvid']}:title",confidence=0.85);r["count"]+=1
    if seeds["audio"]:
        try:wm.observe("audio",seeds["audio"],label=f"bili:{seeds['bvid']}:audio",confidence=0.75);r["count"]+=1
        except:pass
    for fp in seeds["frames"]:
        try:wm.observe("image",fp,label=f"bili:{seeds['bvid']}:frame",confidence=0.7);r["count"]+=1
        except:pass
    if seeds["video"]:
        try:wm.observe("video",seeds["video"],label=f"bili:{seeds['bvid']}:video",confidence=0.7);r["count"]+=1
        except:pass
    return r

def cleanup(seeds:dict):
    for k in["audio","frames","video"]:
        v=seeds.get(k)
        if isinstance(v,list):
            for f in v:
                try:os.remove(f)
                except:pass
        elif v:
            try:os.remove(v)
            except:pass
    bvid=seeds["bvid"]
    for f in os.listdir(VIDEO_CACHE):
        if f.startswith(bvid):
            try:os.remove(str(VIDEO_CACHE/f))
            except:pass

def process_one(bvid:str,title:str="",max_mb:int=80,keep_files:bool=False)->dict|None:
    """处理单个视频: 下→拆→编码→清理."""
    print(f"  [{bvid}] {title[:50]}")
    vp=download(bvid,max_mb=max_mb)
    if not vp:
        print(f"    下载失败, 仅文字种子")
        get_wm().observe("text",title or bvid,label=f"bili:{bvid}:text_only",confidence=0.7)
        return{"bvid":bvid,"seeds":1,"downloaded":False}
    mb=os.path.getsize(vp)/1e6
    print(f"    下载:{mb:.1f}MB ",end="")
    seeds=extract(bvid,vp,title)
    nf=len(seeds["frames"])
    has_a=bool(seeds["audio"])
    print(f"音频:{'Y'if has_a else'N'} 帧:{nf}")
    r=encode(seeds)
    print(f"    -> {r['count']}种子")
    if not keep_files:cleanup(seeds)
    return{"bvid":bvid,"seeds":r["count"],"downloaded":True}

def run(source:str="hot",keyword:str=None,max_videos:int=3,max_mb:int=80)->dict:
    """主入口. source: hot/keyword/bvid"""
    print(f"\n{'='*50}\nB站学习管线: {source}={keyword or '热门'}\n{'='*50}")
    wm=get_wm()
    start=wm.get_stats()["nodes"]

    if source=="bvid" and keyword:
        videos=[{"bvid":keyword,"title":keyword}]
    elif source=="keyword" and keyword:
        print(f"[搜索] {keyword}")
        videos=search_keyword(keyword,max_videos)
    else:
        print(f"[热门榜]")
        videos=search_hot(max_videos)

    if not videos:
        print("无视频")
        return{"ok":False,"error":"no videos"}
    print(f"找到 {len(videos)} 个视频")

    total=0;done=[]
    for v in videos[:max_videos]:
        r=process_one(v["bvid"],v.get("title",""),max_mb)
        if r:total+=r["seeds"];done.append(r)

    end=wm.get_stats()["nodes"]
    print(f"\n完成: {len(done)}视频, {total}种子, WM:{start}->{end}(+{end-start})")
    return{"ok":True,"source":source,"videos":len(done),"seeds":total,"nodes":end}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description="Nexus B站学习管线")
    p.add_argument("--source",default="hot",choices=["hot","keyword","bvid"])
    p.add_argument("--keyword",default=None)
    p.add_argument("--max",type=int,default=2)
    p.add_argument("--mb",type=int,default=80)
    args=p.parse_args()
    run(source=args.source,keyword=args.keyword,max_videos=args.max,max_mb=args.mb)
