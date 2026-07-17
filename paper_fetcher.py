# -*- coding: utf-8 -*-
"""PaperFetcher — arXiv 论文批量下载器 (v18.5n)

触发: 凌晨 2-6AM, 随机偏移 ±30min
来源: arXiv API (http://export.arxiv.org/api/query)
存储: data/research/cache/{date}.json + EvoKG
去重: arxiv_id 唯一键
状态: raw → comprehended → hypothesized → verified → integrated

与 ResearchEngine 解耦:
  下载失败不影响研究 (用库存)
  研究卡住不影响下载 (凌晨照样囤)
"""

import gzip
import hashlib
import json
import logging
import os
import random
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("nexus.research")

NEXUS_HOME = Path(__file__).parent.parent
CACHE_DIR = NEXUS_HOME / "data" / "research" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = NEXUS_HOME / "data" / "research" / "paper_state.json"
ARXIV_API = "http://export.arxiv.org/api/query"
UA = "Nexus/2.0 PaperFetcher"

# 领域+关键词 (与 ResearchEngine 共享)
DOMAINS = {
    "ai": ["machine learning", "deep learning", "reinforcement learning",
           "transformer attention", "autonomous agent", "self improving AI",
           "neural architecture", "continual learning"],
    "systems": ["distributed systems", "compiler optimization",
                "parallel computing", "GPU acceleration"],
    "math": ["optimization theory", "probability statistics",
             "information theory", "graph theory algorithms"],
    "neuroscience": ["free energy principle", "predictive coding",
                     "active inference", "synaptic plasticity"],
}

PAPER_STATUSES = ["raw", "comprehended", "hypothesized", "verified", "integrated"]


class PaperFetcher:
    """凌晨批量下载 arXiv 论文。"""

    def __init__(self):
        self._state = self._load_state()
        self._today_papers: List[Dict] = []

    # ── 主入口 ──────────────────────────────────────────────────

    def should_fetch(self) -> bool:
        """检查是否到了下载窗口 (凌晨2-6AM, 随机偏移)。"""
        now = datetime.now()
        hour = now.hour
        if hour < 2 or hour >= 6:
            return False
        # 上次下载 > 23h?
        last = self._state.get("last_fetch_ts", 0)
        if time.time() - last < 23 * 3600:
            return False
        # 随机偏移 ±30min
        offset = self._state.get("fetch_offset", random.randint(-1800, 1800))
        if "fetch_offset" not in self._state:
            self._state["fetch_offset"] = offset
            self._save_state()
        target = (hour * 3600 + now.minute * 60 + now.second) + offset
        return 120 <= target <= 300  # 2min-5min 窗口

    def fetch_all(self, papers_per_domain: int = 15) -> Dict:
        """批量下载所有领域论文。"""
        result = {"total": 0, "new": 0, "by_domain": {}, "errors": []}

        for domain, keywords in DOMAINS.items():
            domain_papers = []
            for kw in keywords[:3]:  # 每域取3个关键词
                try:
                    papers = self._fetch_arxiv(kw, max_results=papers_per_domain // 3 + 3)
                    domain_papers.extend(papers)
                except Exception as e:
                    result["errors"].append(f"{domain}/{kw}: {e}")
                    logger.debug("[PaperFetcher] %s/%s failed: %s", domain, kw, e)

            # 去重
            seen = set()
            unique = []
            existing_ids = self._state.get("downloaded_ids", set())
            for p in domain_papers:
                if p["arxiv_id"] not in seen and p["arxiv_id"] not in existing_ids:
                    seen.add(p["arxiv_id"])
                    p["domain"] = domain
                    p["status"] = "raw"
                    p["fetched_at"] = time.time()
                    unique.append(p)
                    existing_ids.add(p["arxiv_id"])

            result["by_domain"][domain] = len(unique)
            result["new"] += len(unique)
            result["total"] += len(domain_papers)
            self._today_papers.extend(unique)

        # 持久化
        if self._today_papers:
            self._save_cache()
            self._save_to_evokg()
            self._state["downloaded_ids"] = list(existing_ids)[-5000:]  # 保留最近5000个
            self._state["last_fetch_ts"] = time.time()
            self._state["total_downloaded"] = self._state.get("total_downloaded", 0) + result["new"]
            self._save_state()

        result["skipped"] = result["total"] - result["new"]
        logger.info("[PaperFetcher] %d new / %d total / %d skipped",
                   result["new"], result["total"], result["skipped"])
        return result

    def get_inventory(self, status: str = None, domain: str = None, limit: int = 50) -> List[Dict]:
        """查询本地论文库存。"""
        papers = self._load_all_cache()
        if status:
            papers = [p for p in papers if p.get("status") == status]
        if domain:
            papers = [p for p in papers if p.get("domain") == domain]
        papers.sort(key=lambda p: p.get("fetched_at", 0), reverse=True)
        return papers[:limit]

    def update_status(self, arxiv_id: str, new_status: str):
        """更新论文状态 (raw→comprehended→...)。"""
        if new_status not in PAPER_STATUSES:
            return
        # 更新缓存文件
        for cache_file in sorted(CACHE_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                for p in data:
                    if p.get("arxiv_id") == arxiv_id:
                        p["status"] = new_status
                        p["status_updated"] = time.time()
                        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
                        return
            except Exception:
                pass

    # ── 内部方法 ──────────────────────────────────────────────────

    def _fetch_arxiv(self, query: str, max_results: int = 10) -> List[Dict]:
        """调用 arXiv API 搜索论文。"""
        encoded = urllib.parse.quote(query)
        url = f"{ARXIV_API}?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance"
        req = urllib.request.Request(url, headers={"User-Agent": UA})

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        root = ET.fromstring(raw)
        papers = []

        for entry in root.findall("atom:entry", ns):
            try:
                aid = entry.find("atom:id", ns).text.split("/")[-1]
                title = " ".join(entry.find("atom:title", ns).text.split())
                authors = [a.find("atom:name", ns).text
                          for a in entry.findall("atom:author", ns)][:5]
                abstract = " ".join(entry.find("atom:summary", ns).text.split())
                published = entry.find("atom:published", ns).text[:10]
                cats = [c.get("term") for c in entry.findall("atom:category", ns)]

                papers.append({
                    "arxiv_id": aid, "title": title, "authors": authors,
                    "abstract": abstract, "published": published,
                    "categories": cats, "query": query,
                    "content_hash": hashlib.md5((title + abstract[:200]).encode()).hexdigest()[:16],
                })
            except Exception:
                continue

        return papers

    def _save_cache(self):
        """存到 JSON 缓存文件。"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        cache_file = CACHE_DIR / f"{date_str}.json"

        existing = []
        if cache_file.exists():
            try:
                existing = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        all_papers = existing + self._today_papers
        # 去重合并
        seen = {}
        for p in existing:
            seen[p["arxiv_id"]] = p
        for p in self._today_papers:
            seen[p["arxiv_id"]] = p
        merged = list(seen.values())

        cache_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_to_evokg(self):
        """同步到 EvoKG (可选, 不影响核心流程)。"""
        try:
            from nexus_agent.evokg import get_evokg
            kg = get_evokg()
            SubgraphType = __import__('nexus_agent.evokg', fromlist=['SubgraphType']).SubgraphType
            for p in self._today_papers[:20]:  # 限制数量
                kg.add_node(
                    subgraph=SubgraphType.DOMAIN_KNOWLEDGE,
                    content=f"[{p['domain']}] {p['title']}: {p['abstract'][:500]}",
                    confidence=0.7,
                    metadata={"arxiv_id": p["arxiv_id"], "source": "paper_fetcher"},
                )
        except Exception:
            logger.debug("EvoKG sync skipped", exc_info=True)

    def _load_all_cache(self) -> List[Dict]:
        """加载所有缓存论文。"""
        papers = []
        for f in sorted(CACHE_DIR.glob("*.json")):
            try:
                papers.extend(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return papers

    def _load_state(self) -> Dict:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                data["downloaded_ids"] = set(data.get("downloaded_ids", []))
                return data
            except Exception:
                pass
        return {"downloaded_ids": set(), "last_fetch_ts": 0, "total_downloaded": 0}

    def _save_state(self):
        data = dict(self._state)
        data["downloaded_ids"] = list(data["downloaded_ids"])[:5000]
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── Singleton ─────────────────────────────────────────────

_fetcher: Optional[PaperFetcher] = None


def get_paper_fetcher() -> PaperFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = PaperFetcher()
    return _fetcher
