# -*- coding: utf-8 -*-
"""
Nexus BiliBili Pipeline — 自主B站视频发现+下载管道.
==================================================

流程:
  search_videos(keyword) → B站API搜索
  → get_video_info(bvid) 获取元数据
  → RateLimiter 限速检查 (1 video / 15 min)
  → download_video(bvid) yt-dlp下载 (max 720p, 500MB)
  → seed_extractor 多模态种子提取

全异步, 零人工.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimiter — 限速控制, 同一视频15分钟冷却
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RateLimiter:
    """下载限速器: 最多每15分钟下载1个视频, 防止对B站服务器造成压力."""

    cooldown_seconds: float = 900.0  # 15 minutes
    _last_download: float = 0.0
    _download_history: Dict[str, float] = field(default_factory=dict)  # bvid → timestamp

    @property
    def last_download_timestamp(self) -> float:
        """上次下载的 Unix 时间戳."""
        return self._last_download

    @property
    def time_since_last_download(self) -> float:
        """距离上次下载已过秒数."""
        if self._last_download == 0.0:
            return float("inf")
        return time.time() - self._last_download

    @property
    def cooldown_remaining(self) -> float:
        """冷却剩余秒数."""
        elapsed = self.time_since_last_download
        if elapsed >= self.cooldown_seconds:
            return 0.0
        return max(0.0, self.cooldown_seconds - elapsed)

    def can_download(self) -> bool:
        """是否允许下载."""
        return self.time_since_last_download >= self.cooldown_seconds

    def record_download(self, bvid: str) -> None:
        """记录一次下载."""
        now = time.time()
        self._last_download = now
        self._download_history[bvid] = now
        logger.info(
            "[RateLimiter] Recorded download: %s (next allowed after %.0fs)",
            bvid, self.cooldown_seconds,
        )

    async def wait_if_needed(self) -> float:
        """如果需要冷却, 异步等待; 返回等待秒数."""
        remaining = self.cooldown_remaining
        if remaining > 0:
            logger.info(
                "[RateLimiter] Cooldown: waiting %.1fs before next download...",
                remaining,
            )
            await asyncio.sleep(remaining)
        return remaining

    def was_downloaded(self, bvid: str) -> bool:
        """检查某个视频是否已下载过."""
        return bvid in self._download_history

    def get_download_count(self) -> int:
        """获取历史下载总数."""
        return len(self._download_history)

    def reset(self) -> None:
        """重置限速器状态."""
        self._last_download = 0.0
        self._download_history.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Search keywords per modality
# ═══════════════════════════════════════════════════════════════════════════════

MODALITY_KEYWORDS: Dict[str, List[str]] = {
    "code": [
        "Python教程",
        "编程入门",
        "算法讲解",
        "LeetCode刷题",
        "机器学习实战",
        "深度学习",
    ],
    "text": [
        "科普",
        "历史",
        "哲学",
        "文学解读",
        "经济学原理",
        "心理学入门",
    ],
    "audio": [
        "访谈",
        "演讲",
        "播客",
        "TED演讲",
        "圆桌讨论",
        "电台节目",
    ],
    "image": [
        "摄影",
        "绘画",
        "设计",
        "调色教程",
        "构图技巧",
        "美食拍摄",
    ],
    "video": [
        "纪录片",
        "动画短片",
        "电影解说",
        "旅行Vlog",
        "自然风光",
        "城市漫步",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# B站 VideoInfo dataclass
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BiliVideoInfo:
    """B站视频元数据."""
    bvid: str
    title: str = ""
    description: str = ""
    duration_seconds: int = 0
    tags: List[str] = field(default_factory=list)
    play_count: int = 0
    like_count: int = 0
    author: str = ""
    cover_url: str = ""
    url: str = ""

    @property
    def url(self) -> str:  # type: ignore[override]
        return f"https://www.bilibili.com/video/{self.bvid}"


# ═══════════════════════════════════════════════════════════════════════════════
# BiliBiliPipeline — 搜索 + 下载 + 限速
# ═══════════════════════════════════════════════════════════════════════════════

class BiliBiliPipeline:
    """B站视频发现与下载管道.

    用法:
        pipeline = BiliBiliPipeline()
        results = await pipeline.search_videos("Python教程", max_results=5)
        for video in results:
            info = await pipeline.get_video_info(video["bvid"])
            path = await pipeline.download_video(video["bvid"], "./downloads")
    """

    SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
    VIDEO_INFO_API = "https://api.bilibili.com/x/web-interface/view"

    # 常见 User-Agent, 避免被B站API限流
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(self, output_dir: str | None = None):
        self._rate_limiter = RateLimiter()
        self._output_dir = Path(output_dir) if output_dir else Path.home() / ".nexus" / "bilibili_videos"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._session: Any = None
        self._stats = {
            "searches": 0,
            "downloads": 0,
            "downloads_failed": 0,
            "total_bytes": 0,
        }

    # ── Search ──────────────────────────────────────────────────────────────
    
    # 轮换UA防反爬
    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    async def search_videos(
        self,
        keyword: str,
        max_results: int = 5,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """搜索B站视频 (curl+yt-dlp双通道, 智能退避)."""
        import subprocess, json, urllib.parse, random, asyncio, tempfile, os

        self._stats["searches"] += 1
        results: List[Dict[str, Any]] = []

        encoded = urllib.parse.quote(keyword)
        
        # 先获取 B站 cookie (避免 412 反爬)
        cookie_jar = tempfile.mktemp(suffix='.txt')
        for attempt in range(3):
            ua = random.choice(self._USER_AGENTS)
            try:
                # Step 1: 访问首页获取 cookie
                subprocess.run([
                    "curl", "-s", "-c", cookie_jar, "--max-time", "10",
                    "-A", ua, "https://www.bilibili.com/", "-o", os.devnull
                ], timeout=12, capture_output=True)
                # Step 2: 用 cookie 搜索
                r = subprocess.run([
                    "curl", "-s", "-b", cookie_jar, "--max-time", "12",
                    "-A", ua,
                    "-H", "Referer: https://www.bilibili.com/",
                    f"{self.SEARCH_API}?search_type=video&keyword={encoded}&page={page}&order=totalrank"
                ], capture_output=True, text=True, timeout=15)
                
                out = r.stdout.strip()
                if not out or out.startswith("<"):
                    if attempt < 2:
                        await asyncio.sleep(2 + random.random() * 3)
                        continue
                    logger.warning("[BiliPipeline] HTML response for '%s', trying yt-dlp", keyword)
                    return await self._search_ytdlp(keyword, max_results)
                
                data = json.loads(out)
                code = data.get("code", -1)
                if code == 0:
                    break
                elif code == -412:
                    if attempt < 2:
                        await asyncio.sleep(3 + random.random() * 4)
                        continue
                    return await self._search_ytdlp(keyword, max_results)
                else:
                    logger.warning("[BiliPipeline] API code=%d for '%s'", code, keyword)
                    return results
                    
            except json.JSONDecodeError:
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                return await self._search_ytdlp(keyword, max_results)
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                logger.warning("[BiliPipeline] Search error for '%s': %s", keyword, e)
                return results
        
        if 'data' not in dir():
            return results

        result_data = data.get("data", {}).get("result", [])
        for item in result_data[:max_results]:
            bvid = item.get("bvid", "")
            if not bvid:
                continue
            tag_str = item.get("tag", "")
            tags = [t.strip() for t in tag_str.split(",") if t.strip()] if tag_str else []
            duration_str = item.get("duration", "0:00")
            duration_s = self._parse_duration(duration_str)
            results.append({
                "bvid": bvid,
                "title": item.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                "description": item.get("description", ""),
                "duration": duration_s,
                "duration_str": duration_str,
                "tags": tags,
                "play": item.get("play", 0),
                "author": item.get("author", ""),
                "cover": f"https:{item.get('pic', '')}" if item.get("pic", "").startswith("//") else item.get("pic", ""),
            })
        logger.info("[BiliPipeline] Search '%s' → %d results (attempt %d)", keyword, len(results), attempt + 1)
        return results

    async def _search_ytdlp(self, keyword: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """yt-dlp fallback search."""
        import subprocess, json
        results = []
        try:
            r = subprocess.run([
                "yt-dlp", "--dump-json", "--flat-playlist",
                f"ytsearch{max_results}:{keyword}"
            ], capture_output=True, text=True, timeout=30)
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    results.append({
                        "bvid": item.get("id", ""),
                        "title": item.get("title", "")[:200],
                        "description": item.get("description", "")[:500],
                        "duration": item.get("duration", 0),
                        "duration_str": f"{item.get('duration',0)//60}:{item.get('duration',0)%60:02d}",
                        "tags": item.get("tags", []),
                        "play": item.get("view_count", 0),
                        "author": item.get("uploader", ""),
                        "cover": item.get("thumbnail", ""),
                    })
                except json.JSONDecodeError:
                    continue
            if results:
                logger.info("[BiliPipeline] yt-dlp search '%s' → %d results", keyword, len(results))
        except Exception as e:
            logger.warning("[BiliPipeline] yt-dlp search failed: %s", e)
        return results

    def _parse_duration(self, duration_str: str) -> int:
        """解析 'mm:ss' 或 'hh:mm:ss' → 秒数."""
        parts = duration_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0

    # ── Video Info ──────────────────────────────────────────────────────────

    async def get_video_info(self, bvid: str) -> BiliVideoInfo:
        """获取B站视频详细信息.

        Args:
            bvid: B站视频 BV号

        Returns:
            BiliVideoInfo dataclass
        """
        import aiohttp

        params = {"bvid": bvid}
        headers = {
            "User-Agent": self.USER_AGENT,
            "Referer": f"https://www.bilibili.com/video/{bvid}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.VIDEO_INFO_API,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.warning("[BiliPipeline] Video info HTTP %d for %s", resp.status, bvid)
                        return BiliVideoInfo(bvid=bvid)

                    data = await resp.json()

            code = data.get("code", -1)
            if code != 0:
                logger.warning("[BiliPipeline] Video info error code=%d for %s", code, bvid)
                return BiliVideoInfo(bvid=bvid)

            video_data = data.get("data", {})
            return BiliVideoInfo(
                bvid=bvid,
                title=video_data.get("title", ""),
                description=video_data.get("desc", ""),
                duration_seconds=video_data.get("duration", 0),
                tags=[],
                play_count=video_data.get("stat", {}).get("view", 0),
                like_count=video_data.get("stat", {}).get("like", 0),
                author=video_data.get("owner", {}).get("name", ""),
                cover_url=video_data.get("pic", ""),
            )

        except asyncio.TimeoutError:
            logger.warning("[BiliPipeline] Video info timeout for %s", bvid)
        except Exception as e:
            logger.warning("[BiliPipeline] Video info failed for %s: %s", bvid, e)

        return BiliVideoInfo(bvid=bvid)

    # ── Download ────────────────────────────────────────────────────────────

    async def download_video(
        self,
        bvid: str,
        output_dir: str | None = None,
        force: bool = False,
    ) -> Optional[str]:
        """下载B站视频 (yt-dlp, max 720p, max 500MB).

        Args:
            bvid: B站视频 BV号
            output_dir: 输出目录, 默认 self._output_dir
            force: 是否跳过限速检查

        Returns:
            下载文件路径, 失败返回 None
        """
        # Rate limit check
        if not force and not self._rate_limiter.can_download():
            remaining = self._rate_limiter.cooldown_remaining
            logger.info(
                "[BiliPipeline] Rate limited: %ds remaining. Waiting...",
                int(remaining),
            )
            await self._rate_limiter.wait_if_needed()

        dest_dir = Path(output_dir) if output_dir else self._output_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = f"https://www.bilibili.com/video/{bvid}"
        output_template = str(dest_dir / f"%(title)s_{bvid}.%(ext)s")

        # yt-dlp args: 720p max, 500MB max, merge to mp4
        cmd = [
            "yt-dlp",
            url,
            "--output", output_template,
            "--format", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--max-filesize", "500M",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--user-agent", self.USER_AGENT,
            "--socket-timeout", "30",
            "--retries", "3",
        ]

        logger.info("[BiliPipeline] Downloading %s → %s", bvid, dest_dir)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600,  # 10 minute download timeout
            )

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
                logger.warning(
                    "[BiliPipeline] yt-dlp failed for %s (rc=%d): %s",
                    bvid, process.returncode, stderr_text[:300],
                )
                self._stats["downloads_failed"] += 1
                return None

            # Find the downloaded file
            downloaded_file = await self._find_downloaded_file(dest_dir, bvid)
            if downloaded_file:
                file_size = os.path.getsize(downloaded_file)
                self._stats["total_bytes"] += file_size
                self._stats["downloads"] += 1
                self._rate_limiter.record_download(bvid)
                logger.info(
                    "[BiliPipeline] Downloaded %s (%.1f MB) → %s",
                    bvid, file_size / (1024 * 1024),
                    os.path.basename(downloaded_file),
                )
                return downloaded_file
            else:
                logger.warning("[BiliPipeline] Download seemed ok but couldn't find file for %s", bvid)
                self._stats["downloads_failed"] += 1
                return None

        except asyncio.TimeoutError:
            logger.warning("[BiliPipeline] Download timeout for %s", bvid)
            self._stats["downloads_failed"] += 1
            return None
        except FileNotFoundError:
            logger.error(
                "[BiliPipeline] yt-dlp not found. Install: pip install yt-dlp"
            )
            self._stats["downloads_failed"] += 1
            return None
        except Exception as e:
            logger.warning("[BiliPipeline] Download error for %s: %s", bvid, e)
            self._stats["downloads_failed"] += 1
            return None

    async def _find_downloaded_file(self, directory: Path, bvid: str) -> Optional[str]:
        """在目录中查找刚下载的文件 (通过 bvid 匹配)."""
        # 按修改时间排序, 找最近的匹配文件
        try:
            candidates = []
            for f in directory.iterdir():
                if f.is_file() and f.suffix.lower() in (".mp4", ".mkv", ".webm", ".flv"):
                    if bvid in f.stem or bvid in f.name:
                        candidates.append((f.stat().st_mtime, str(f)))

            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]
        except Exception:
            pass
        return None

    # ── Batch Download per Modality ─────────────────────────────────────────

    async def discover_and_download(
        self,
        modality: str,
        max_videos: int = 3,
        output_dir: str | None = None,
    ) -> List[Dict[str, Any]]:
        """按模态发现并下载视频.

        Args:
            modality: 模态名称 (code, text, audio, image, video)
            max_videos: 每种模态最多下载视频数
            output_dir: 输出目录

        Returns:
            [{bvid, title, file_path, modality, ...}]
        """
        keywords = MODALITY_KEYWORDS.get(modality, [])
        if not keywords:
            logger.warning("[BiliPipeline] Unknown modality: %s", modality)
            return []

        results: List[Dict[str, Any]] = []
        videos_to_download: List[Dict[str, Any]] = []

        # Phase 1: Search across keywords
        for keyword in keywords:
            if len(videos_to_download) >= max_videos:
                break

            search_results = await self.search_videos(keyword, max_results=3)
            for item in search_results:
                bvid = item["bvid"]
                if not self._rate_limiter.was_downloaded(bvid):
                    item["modality"] = modality
                    item["search_keyword"] = keyword
                    videos_to_download.append(item)
                    if len(videos_to_download) >= max_videos:
                        break

        # Phase 2: Download (rate-limited)
        for item in videos_to_download:
            file_path = await self.download_video(item["bvid"], output_dir)
            if file_path:
                item["file_path"] = file_path
                item["downloaded_at"] = time.time()
                results.append(item)

            # Emit event for each seed-ready video
            try:
                from nexus_agent.event_bus import get_event_bus
                bus = get_event_bus()
                bus.publish(
                    "seed.video_ready",
                    {
                        "bvid": item["bvid"],
                        "title": item.get("title", ""),
                        "file_path": file_path,
                        "modality": modality,
                    },
                    source="bilibili_pipeline",
                )
            except Exception:
                pass

        logger.info(
            "[BiliPipeline] discover_and_download(%s): %d/%d downloaded",
            modality, len(results), len(videos_to_download),
        )
        return results

    # ── Stats ───────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取管道统计."""
        return {
            **self._stats,
            "rate_limiter": {
                "cooldown_s": self._rate_limiter.cooldown_seconds,
                "last_download": self._rate_limiter.last_download_timestamp,
                "remaining_s": self._rate_limiter.cooldown_remaining,
                "total_downloads": self._rate_limiter.get_download_count(),
            },
        }

    def get_modality_keywords(self) -> Dict[str, List[str]]:
        """获取各模态搜索关键词."""
        return dict(MODALITY_KEYWORDS)

    async def download_from_url(self, url: str, output_dir: str = None) -> Optional[Dict]:
        """从任意URL下载视频 (B站/抖音/YouTube等, yt-dlp支持的全部平台).
        
        Returns: {file_path, title, duration, bvid/url, ...} or None
        """
        import subprocess, json, tempfile
        od = output_dir or str(self.nexus_home / "data" / "videos" / "incoming")
        Path(od).mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run([
                "yt-dlp", "--dump-json", "--no-download", url
            ], capture_output=True, text=True, timeout=20)
            info = json.loads(r.stdout) if r.stdout.strip() else {}
            title = info.get("title", "video")[:80]
            
            # Download
            out_tmpl = str(Path(od) / f"%(title).80s.%(ext)s")
            r2 = subprocess.run([
                "yt-dlp", "-f", "best[height<=720]", "--max-filesize", "500M",
                "-o", out_tmpl, url
            ], capture_output=True, text=True, timeout=600)
            
            # Find the downloaded file
            import glob as _glob
            files = sorted(_glob.glob(str(Path(od) / "*.mp4")) + 
                          _glob.glob(str(Path(od) / "*.mkv")) +
                          _glob.glob(str(Path(od) / "*.webm")),
                          key=lambda x: Path(x).stat().st_mtime, reverse=True)
            if files:
                logger.info("[BiliPipeline] Downloaded: %s → %s", url[:60], files[0])
                return {"file_path": files[0], "title": title, "url": url}
        except Exception as e:
            logger.warning("[BiliPipeline] Download failed for %s: %s", url[:60], e)
        return None

    async def feed_text(self, text: str, source: str = "manual") -> Dict:
        """直接喂文本: 编码→LLM分析→世界模型 (不下载视频).
        
        适用场景: 抖音/网页/论文摘要等无法下载的文字内容。
        """
        result = {"status": "ok", "analysis": "", "nodes_added": 0}
        try:
            from nexus_agent.nexus_llm import NexusLLM
            llm = NexusLLM()
            resp = await llm.achat(messages=[{
                "role": "user",
                "content": f"从以下内容提取3-5个关键知识点，每条一句话，用中文:\n{text[:2000]}"
            }], max_tokens=300)
            result["analysis"] = resp[:500] if resp else ""
            
            from nexus_agent.neural.encoders import get_encoder_hub
            vec = get_encoder_hub().encode(text[:500], "text")
            
            from nexus_agent.world_model import get_world_model
            wm = get_world_model()
            nid = wm.observe("text", {"text": text[:1000], "analysis": result["analysis"]},
                            label=f"{source}_{text[:40].strip()}")
            if nid: result["nodes_added"] = 1
            if hasattr(wm, 'space') and wm.space: wm.space._save()
        except Exception as e:
            result["status"] = f"error: {e}"
        return result

    async def analyze_and_feed(self, video_path: str) -> Dict:
        """下载→提取种子→LLM分析→喂世界模型 (全链路).
        
        Returns: {status, seeds, analysis, nodes_added}
        """
        result = {"status": "ok", "seeds": 0, "nodes_added": 0, "analysis": ""}
        try:
            # 1. 提取种子
            from nexus_agent.autonomous.seed_extractor import MultiModalSeedExtractor
            se = MultiModalSeedExtractor()
            seeds = await se.extract_all(video_path)
            result["seeds"] = len(seeds)
            
            # 2. LLM分析内容
            text_content = ""
            for name, seed in seeds.items():
                if hasattr(seed, 'data') and isinstance(seed.data, dict):
                    text_content += str(seed.data.get("text", ""))[:2000]
            if text_content:
                try:
                    from nexus_agent.llm_client import get_llm_client
                    llm = get_llm_client()
                    resp = await llm.achat(messages=[{
                        "role": "user", 
                        "content": f"分析以下视频内容，提取3个关键知识点并简要说明：\n{text_content[:1500]}"
                    }], max_tokens=300)
                    result["analysis"] = resp[:500] if resp else ""
                except Exception as e:
                    result["analysis"] = f"LLM分析失败: {e}"
            
            # 3. 喂世界模型
            from nexus_agent.world_model import get_world_model
            wm = get_world_model()
            for name, seed in seeds.items():
                nid = wm.observe(seed.modality, seed.data, 
                                label=f"{Path(video_path).stem}_{name}")
                if nid:
                    result["nodes_added"] += 1
            
            # 4. 持久化
            if hasattr(wm, 'space') and wm.space:
                wm.space._save()
                
        except Exception as e:
            result["status"] = f"error: {e}"
        return result

    async def download_for_user_interests(
        self,
        user_model=None,
        max_videos: int = 3,
        output_dir: str | None = None,
    ) -> List[Dict[str, Any]]:
        """根据用户兴趣驱动B站下载。无兴趣时自主决策."""
        interests = {}
        if user_model is None:
            try:
                from nexus_agent.agent_init import _get_agent_singleton
                agent = _get_agent_singleton()
                if agent and hasattr(agent, 'user_model') and agent.user_model:
                    interests = agent.user_model.get_model().get('interests', {})
            except Exception:
                pass
        else:
            interests = user_model.get_model().get('interests', {})
        
        if not interests:
            logger.info("[BiliPipeline] 无用户兴趣，自主决策→编程+科普")
            interests = {"编程": 0.5, "科普": 0.5}
        
        sorted_i = sorted(interests.items(), key=lambda x: -x[1])
        top = [d for d, w in sorted_i[:5] if w > 0.2]
        all_results = []
        for domain in top:
            modality = INTEREST_TO_MODALITY.get(domain, "text")
            # 直接用兴趣域名作为搜索词（UserModel提取什么就搜什么）
            # 同时保留静态关键词做补充
            keywords = [domain] + MODALITY_KEYWORDS.get(modality, [])[:2]
            for kw in keywords[:2]:  # 每个domain最多搜2个词
                try:
                    r = await self.discover_and_download(modality=modality, max_videos=1, output_dir=output_dir)
                    all_results.extend(r)
                    break  # 搜到一个就跳到下一个domain
                except Exception:
                    continue
            if len(all_results) >= max_videos:
                break
        logger.info("[BiliPipeline] 兴趣下载: %d videos for %s", len(all_results), top[:3])
        return all_results


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════════

_pipeline_instance: Optional[BiliBiliPipeline] = None


def get_bilibili_pipeline() -> BiliBiliPipeline:
    """获取 BiliBiliPipeline 单例."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = BiliBiliPipeline()
    return _pipeline_instance


# ── v∞.14: 用户兴趣 → 模态关键词映射 ──
INTEREST_TO_MODALITY: Dict[str, str] = {
    "股票": "text", "交易": "text", "投资": "text", "金融": "text",
    "编程": "code", "代码": "code", "Python": "code", "算法": "code",
    "AI": "code", "机器学习": "code", "深度学习": "code", "NLP": "code",
    "摄影": "image", "绘画": "image", "设计": "image", "艺术": "image",
    "中医": "text", "医学": "text", "健康": "text", "养生": "text",
    "音乐": "audio", "播客": "audio", "访谈": "audio",
    "电影": "video", "动画": "video", "纪录片": "video",
}


logger.info("[BiliPipeline] Ready: search → rate-limit → yt-dlp download (max 720p / 500MB)")
