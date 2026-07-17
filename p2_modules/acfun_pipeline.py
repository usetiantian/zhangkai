# -*- coding: utf-8 -*-
"""
Nexus AcFun Pipeline — A站视频发现+下载管道 (v18)
=================================================
搜索 → 下载(yt-dlp) → 拆解(ffmpeg) → 编码(5模态) → WorldModel

API: 完全开放, 无需登录, 无412反爬
"""
import asyncio, json, logging, os, re, subprocess, gzip, time
import urllib.request, urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NEXUS_HOME = Path(__file__).parent.parent
VIDEO_CACHE = NEXUS_HOME / "data" / "videos" / "acfun"
VIDEO_CACHE.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class AcVideo:
    id: str; title: str; description: str = ""
    duration_ms: int = 0; view_count: int = 0
    author: str = ""; cover_url: str = ""
    video_url: str = ""


@dataclass
class RateLimiter:
    cooldown_seconds: float = 900.0
    _last: float = 0.0

    @property
    def can_download(self) -> bool:
        return time.time() - self._last >= self.cooldown_seconds

    def record(self):
        self._last = time.time()


class AcFunPipeline:
    """A站视频发现与下载管道."""

    SEARCH_API = "https://www.acfun.cn/rest/pc-direct/search/video"
    VIDEO_API = "https://www.acfun.cn/rest/pc-direct/video/info"
    _downloading = False

    def __init__(self):
        self._rate_limiter = RateLimiter()
        self._stats = {"searches": 0, "downloads": 0, "downloads_failed": 0}

    def _fetch(self, url: str) -> dict:
        """HTTP GET with gzip support."""
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Referer": "https://www.acfun.cn/",
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
            if len(raw) >= 2 and raw[0] == 0x1f and raw[1] == 0x8b:
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8", errors="replace"))

    async def search(self, keyword: str, max_results: int = 5) -> List[AcVideo]:
        """搜索A站视频."""
        self._stats["searches"] += 1
        videos = []
        try:
            kw = urllib.parse.quote(keyword)
            url = f"{self.SEARCH_API}?keyword={kw}&page=1&size={max_results}"
            data = self._fetch(url)
            for item in data.get("videoList", [])[:max_results]:
                videos.append(AcVideo(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    duration_ms=item.get("duration", 0),
                    view_count=item.get("viewCount", 0),
                    author=item.get("user", {}).get("name", ""),
                    cover_url=item.get("coverUrl", ""),
                ))
            logger.info("[AcFun] Search '%s': %d results", keyword, len(videos))
        except Exception as e:
            logger.warning("[AcFun] Search failed: %s", e)
        return videos

    async def get_info(self, video_id: str) -> Optional[AcVideo]:
        """获取视频详情."""
        try:
            url = f"{self.VIDEO_API}?videoId={video_id}"
            data = self._fetch(url)
            info = data.get("video", data)
            return AcVideo(
                id=str(info.get("id", video_id)),
                title=info.get("title", ""),
                description=info.get("description", ""),
                duration_ms=info.get("duration", 0),
                view_count=info.get("viewCount", 0),
                author=info.get("user", {}).get("name", ""),
                cover_url=info.get("coverUrl", ""),
            )
        except Exception as e:
            logger.warning("[AcFun] Info failed: %s", e)
            return None

    async def download(self, video_id: str, max_mb: int = 80) -> Optional[str]:
        """下载视频 (yt-dlp)."""
        if not self._rate_limiter.can_download:
            logger.info("[AcFun] Rate limited, skip")
            return None

        url = f"https://www.acfun.cn/v/ac{video_id}"
        out = str(VIDEO_CACHE / f"{video_id}.mp4")

        try:
            r = subprocess.run([
                "yt-dlp", "-f", f"best[filesize<{max_mb}M]/worst[filesize<{max_mb}M]",
                "-o", out, "--no-playlist", "--quiet", "--no-warnings", url,
            ], capture_output=True, text=True, timeout=120)

            if os.path.exists(out) and os.path.getsize(out) > 10000:
                self._rate_limiter.record()
                self._stats["downloads"] += 1
                logger.info("[AcFun] Downloaded: %s (%.1fMB)", video_id, os.path.getsize(out)/1e6)
                return out
            else:
                self._stats["downloads_failed"] += 1
                return None
        except Exception as e:
            self._stats["downloads_failed"] += 1
            logger.warning("[AcFun] Download failed: %s", e)
            return None

    async def extract_seeds(self, video_path: str, video_id: str, title: str) -> dict:
        """拆解视频 → 音频+关键帧."""
        wd = Path(video_path).parent
        seeds = {"id": video_id, "title": title, "text": title, "audio": None, "frames": [], "video": video_path}

        # 音频
        ap = str(wd / f"ac_{video_id}_audio.wav")
        try:
            subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                          "-ar", "16000", "-ac", "1", "-t", "120", ap],
                          capture_output=True, timeout=30)
            if os.path.exists(ap) and os.path.getsize(ap) > 1000:
                seeds["audio"] = ap
        except Exception:
            pass

        # 关键帧
        try:
            fp = str(wd / f"ac_{video_id}_f_%02d.png")
            subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vf", "fps=1/10",
                          "-vframes", "6", fp], capture_output=True, timeout=30)
            for i in range(1, 7):
                p = str(wd / f"ac_{video_id}_f_{i:02d}.png")
                if os.path.exists(p) and os.path.getsize(p) > 100:
                    seeds["frames"].append(p)
        except Exception:
            pass

        return seeds

    async def feed_world_model(self, seeds: dict) -> int:
        """编码种子→WorldModel."""
        try:
            from nexus_agent.world_model import get_world_model
            wm = get_world_model()
            count = 0
            wm.observe("text", seeds["title"], label=f"acfun:{seeds['id']}:title", confidence=0.85); count += 1
            if seeds.get("audio"):
                wm.observe("audio", seeds["audio"], label=f"acfun:{seeds['id']}:audio", confidence=0.75); count += 1
            for fp in seeds.get("frames", []):
                wm.observe("image", fp, label=f"acfun:{seeds['id']}:frame", confidence=0.7); count += 1
            if seeds.get("video"):
                wm.observe("video", seeds["video"], label=f"acfun:{seeds['id']}:video", confidence=0.7); count += 1
            logger.info("[AcFun] Fed %d seeds to WorldModel", count)
            return count
        except Exception as e:
            logger.warning("[AcFun] Feed failed: %s", e)
            return 0

    async def process_one(self, keyword: str, max_mb: int = 80) -> Optional[Dict]:
        """全链路: 搜索→下载→拆解→编码."""
        videos = await self.search(keyword, max_results=1)
        if not videos:
            return None

        v = videos[0]
        logger.info("[AcFun] Processing: %s - %s", v.id, v.title[:50])

        # 下载
        path = await self.download(v.id, max_mb)
        if not path:
            # 仅文字种子
            try:
                from nexus_agent.world_model import get_world_model
                get_world_model().observe("text", f"{v.title} | {v.description}", label=f"acfun:{v.id}:text", confidence=0.7)
            except Exception:
                pass
            return {"id": v.id, "title": v.title, "downloaded": False, "seeds": 1}

        # 拆解
        seeds = await self.extract_seeds(path, v.id, v.title)

        # 编码
        count = await self.feed_world_model(seeds)

        # 清理
        for f in [seeds.get("audio")] + seeds.get("frames", []) + [path]:
            try:
                if f and os.path.exists(f): os.remove(f)
            except Exception:
                pass

        return {"id": v.id, "title": v.title, "downloaded": True, "seeds": count}

    async def run(self, keyword: str = None, max_videos: int = 2) -> Dict:
        """主入口: 兴趣驱动或自主决策."""
        if not keyword:
            try:
                from nexus_agent.agent_init import _get_agent_singleton
                agent = _get_agent_singleton()
                if agent and hasattr(agent, 'user_model') and agent.user_model:
                    interests = agent.user_model.get_model().get('interests', {})
                    if interests:
                        keyword = max(interests, key=interests.get)
            except Exception:
                pass
            if not keyword:
                keyword = "编程"

        if AcFunPipeline._downloading:
            logger.debug("[AcFun] Already downloading, skip")
            return {"status": "skipped", "reason": "already_downloading"}

        AcFunPipeline._downloading = True
        try:
            logger.info("[AcFun] Pipeline start: %s (max=%d)", keyword, max_videos)
            results = []
            for _ in range(max_videos):
                r = await self.process_one(keyword)
                if r: results.append(r)
            return {"status": "ok", "keyword": keyword, "results": results}
        finally:
            AcFunPipeline._downloading = False

    def get_stats(self) -> Dict:
        return {**self._stats, "rate_limiter": {"can_download": self._rate_limiter.can_download}}


_pipeline: Optional[AcFunPipeline] = None

def get_acfun_pipeline() -> AcFunPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AcFunPipeline()
    return _pipeline
