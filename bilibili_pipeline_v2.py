# -*- coding: utf-8 -*-
"""B站视频 -> 多模态种子 -> WorldModel 训练管道"""
import sys,io,os,re,json,time,logging,subprocess,tempfile,hashlib
from pathlib import Path
from dataclasses import dataclass,field
from typing import Optional
if sys.platform=="win32":sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
logger=logging.getLogger("nexus.bilibili_v2")
NEXUS_HOME=Path(__file__).parent.parent
VIDEO_CACHE=NEXUS_HOME/"data"/"videos"
VIDEO_CACHE.mkdir(parents=True,exist_ok=True)

@dataclass
class BVideo:
    bvid:str;title:str;description:str="";tags:list=field(default_factory=list)
    duration:int=0;author:str="";cid:int=0

@dataclass
class VSeeds:
    bvid:str;title:str;text_seed:str="";subtitle_text:str=""
    audio_path:str="";keyframe_paths:list=field(default_factory=list);video_path:str=""

def search_bilibili(keyword:str,limit:int=5)->list:
    import urllib.request,urllib.parse
    url="https://api.bilibili.com/x/web-interface/search/type"
    params=urllib.parse.urlencode({"search_type":"video","keyword":keyword,"page":1,"order":"click"})
    req=urllib.request.Request(f"{url}?{params}",headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.bilibili.com"})
    results=[]
    try:
        with urllib.request.urlopen(req,timeout=10)as resp:data=json.loads(resp.read().decode())
        for item in data.get("data",{}).get("result",[])[:limit]:
            results.append(BVideo(bvid=item.get("bvid",""),title=item.get("title","").replace("<em>","").replace("</em>",""),description=item.get("description",""),tags=item.get("tag","").split(",") if item.get("tag")else[],duration=item.get("duration",0),author=item.get("author","")))
    except Exception as e:logger.warning(f"search err: {e}")
    return results

def get_video_info(bvid:str)->Optional[dict]:
    import urllib.request
    url=f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.bilibili.com"})
    try:
        with urllib.request.urlopen(req,timeout=10)as resp:return json.loads(resp.read().decode()).get("data",{})
    except:return None

def get_subtitle(bvid:str,cid:int)->str:
    import urllib.request
    url=f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.bilibili.com"})
    try:
        with urllib.request.urlopen(req,timeout=10)as resp:data=json.loads(resp.read().decode())
        subs=data.get("data",{}).get("subtitle",{}).get("subtitles",[])
        if subs:
            sub_url=subs[0].get("subtitle_url","")
            if sub_url:
                if sub_url.startswith("//"):sub_url="https:"+sub_url
                req2=urllib.request.Request(sub_url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req2,timeout=10)as resp2:
                    sub_data=json.loads(resp2.read().decode())
                return " ".join(item.get("content","")for item in sub_data.get("body",[]))
    except:pass
    return ""

def download_video(bvid:str,output_dir:str=None,max_mb:int=80)->Optional[str]:
    dest=output_dir or str(VIDEO_CACHE)
    url=f"https://www.bilibili.com/video/{bvid}"
    try:
        out=f"{dest}/{bvid}.mp4"
        result=subprocess.run(["yt-dlp","-f",f"best[filesize<{max_mb}M]/worst[filesize<{max_mb}M]","-o",out,"--no-warnings",url],capture_output=True,timeout=120,encoding="utf-8",errors="ignore")
        if os.path.exists(out) and os.path.getsize(out)>10000:return out
    except:pass
    try:
        import yt_dlp
        opts={"outtmpl":f"{dest}/{bvid}.%(ext)s","format":f"best[filesize<{max_mb}M]/worst[filesize<{max_mb}M]","quiet":True,"no_warnings":True}
        with yt_dlp.YoutubeDL(opts)as ydl:ydl.download([url])
        for f in os.listdir(dest):
            if f.startswith(bvid) and not f.endswith(".part") and os.path.getsize(str(Path(dest)/f))>10000:return str(Path(dest)/f)
    except:pass
    return None

def extract_seeds(video_path:str,bvid:str,title:str)->Optional[VSeeds]:
    seeds=VSeeds(bvid=bvid,title=title,video_path=video_path)
    wd=Path(video_path).parent
    ap=str(wd/f"{bvid}_audio.wav")
    try:
        subprocess.run(["ffmpeg","-y","-i",video_path,"-vn","-acodec","pcm_s16le","-ar","16000","-ac","1","-t","120",ap],capture_output=True,timeout=30)
        if os.path.exists(ap) and os.path.getsize(ap)>1000:seeds.audio_path=ap
    except:pass
    try:
        fp=str(wd/f"{bvid}_frame_%02d.png")
        subprocess.run(["ffmpeg","-y","-i",video_path,"-vf","fps=1/10","-vframes","10",fp],capture_output=True,timeout=30)
        for i in range(1,11):
            p=str(wd/f"{bvid}_frame_{i:02d}.png")
            if os.path.exists(p) and os.path.getsize(p)>100:seeds.keyframe_paths.append(p)
    except:pass
    seeds.text_seed=title
    return seeds

def feed_to_world_model(seeds:VSeeds,subtitle:str="")->dict:
    from nexus_agent.world_model import get_world_model
    wm=get_world_model()
    r={"bvid":seeds.bvid,"seeds":{}}
    if seeds.text_seed:
        wm.observe("text",seeds.text_seed,label=f"bilibili:{seeds.bvid}:title",confidence=0.85)
        r["seeds"]["text_title"]=True
    if subtitle:
        wm.observe("text",subtitle[:2000],label=f"bilibili:{seeds.bvid}:subtitle",confidence=0.8)
        r["seeds"]["text_subtitle"]=True
    if seeds.audio_path:
        try:
            wm.observe("audio",seeds.audio_path,label=f"bilibili:{seeds.bvid}:audio",confidence=0.75)
            r["seeds"]["audio"]=True
        except:pass
    for fp in seeds.keyframe_paths:
        try:
            wm.observe("image",fp,label=f"bilibili:{seeds.bvid}:frame",confidence=0.7)
            r["seeds"]["image"]=r["seeds"].get("image",0)+1
        except:pass
    if seeds.video_path:
        try:
            wm.observe("video",seeds.video_path,label=f"bilibili:{seeds.bvid}:video",confidence=0.7)
            r["seeds"]["video"]=True
        except:pass
    return r

def feedback(keyword:str,bvid:str,seed_count:int):
    try:
        from nexus_agent.event_bus import get_event_bus
        get_event_bus().publish("bilibili.video_processed",{"bvid":bvid,"keyword":keyword,"seeds":seed_count},source="bilibili_v2")
    except:pass
    try:
        from nexus_agent.user_model import get_user_model
        um=get_user_model()
        if hasattr(um,"record_interest"):um.record_interest(keyword,source="bilibili")
    except:pass

def _get_wm():
    from nexus_agent.world_model import get_world_model
    return get_world_model()

def run(keyword:str=None,max_videos:int=2,max_mb:int=60)->dict:
    if not keyword:
        try:
            from nexus_agent.user_model import get_user_model
            keyword=get_user_model().get_top_interest()or"机器学习"
        except:keyword="机器学习"
    print(f"\n{'='*50}\nB站管线: {keyword}\n{'='*50}")
    videos=search_bilibili(keyword,max_videos)
    if not videos:return{"ok":False,"error":"no results"}
    print(f"[搜索] {len(videos)}个视频")
    total=0;done=[]
    for i,v in enumerate(videos,1):
        print(f"\n[{i}/{len(videos)}] {v.bvid} {v.title[:50]}")
        info=get_video_info(v.bvid)
        cid=info.get("cid",0)if info else 0
        sub=get_subtitle(v.bvid,cid)if cid else""
        if sub:print(f"  字幕:{len(sub)}字")
        txt=f"{v.title} | {v.description} | {' '.join(v.tags)}"
        print(f"  下载中...")
        vp=download_video(v.bvid,max_mb=max_mb)
        if vp:
            print(f"  下载OK:{os.path.getsize(vp)/1e6:.1f}MB")
            seeds=extract_seeds(vp,v.bvid,v.title)
            seeds.text_seed=f"{v.title} | {' '.join(v.tags)}"
            seeds.subtitle_text=sub
            r=feed_to_world_model(seeds,sub)
            sc=sum((1 if isinstance(x,bool)and x else x)for x in r["seeds"].values())
            total+=sc;done.append({"bvid":v.bvid,"seeds":sc})
            feedback(keyword,v.bvid,sc)
            for f in[seeds.audio_path]+seeds.keyframe_paths+[vp]:
                try:os.remove(f)
                except:pass
        else:
            print(f"  下载失败,仅用文字")
            wm=_get_wm()
            wm.observe("text",txt[:1000],label=f"bilibili:{v.bvid}:text",confidence=0.8)
            if sub:wm.observe("text",sub[:2000],label=f"bilibili:{v.bvid}:subtitle",confidence=0.8)
            done.append({"bvid":v.bvid,"seeds":"text_only"})
    wm=_get_wm()
    print(f"\n{'='*50}\n完成:{len(done)}视频,{total}种子,{wm.get_stats()['nodes']}nodes\n{'='*50}")
    return{"ok":True,"keyword":keyword,"videos":len(done),"seeds":total,"nodes":wm.get_stats()["nodes"],"details":done}

if __name__=="__main__":
    kw=sys.argv[1]if len(sys.argv)>1 else"机器学习"
    r=run(keyword=kw,max_videos=2,max_mb=50)
    print(json.dumps(r,ensure_ascii=False,indent=2))
