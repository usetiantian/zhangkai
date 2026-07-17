# -*- coding: utf-8 -*-
"""ExternalFetcher — 统一外部知识下载器 (v18.5n)

凌晨 3-5AM 批量抓取四条数据源:
  1. arXiv      → data/external/papers/     (学术研究专用, 15天清理)
  2. GitHub     → data/external/code/YYYY-MM-DD/   (研究完立即删)
  3. akshare    → data/external/finance/YYYY-MM-DD/ (研究完立即删)
  4. Python文档 → data/external/math/YYYY-MM-DD/    (研究完立即删)

研究消费完 → 反馈删除 → state记录去重 → 明天不再下载
"""

import hashlib, json, logging, os, random, re, ssl, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("nexus.external")

NEXUS_HOME = Path(__file__).parent.parent
EXTERNAL_DIR = NEXUS_HOME / "data" / "external"
STATE_FILE = EXTERNAL_DIR / "fetcher_state.json"
UA = "Nexus/2.0 ExternalFetcher"

# ═══════════════════════════════════════════════
# 论文域 (学术研究专用, 独立目录)
# ═══════════════════════════════════════════════

PAPER_DOMAINS = {
    "ai": ["machine learning transformer", "deep learning optimization",
           "reinforcement learning agent", "autonomous AI self-improving"],
    "systems": ["distributed systems", "compiler optimization",
                "parallel computing GPU"],
    "math": ["optimization theory algorithm", "probability statistics",
             "graph theory", "information theory"],
    "neuroscience": ["free energy principle", "predictive coding",
                     "active inference", "synaptic plasticity"],
    "finance": ["quantitative finance model", "stock market prediction",
                "risk management portfolio"],
    "tcm": ["traditional Chinese medicine herb", "acupuncture mechanism",
            "Chinese herbal medicine pharmacology"],
    "programming": ["programming language design", "software engineering",
                    "Python code analysis", "type system"],
}

# ═══════════════════════════════════════════════
# 代码域 (SelfPlay/KnowledgeGen 消费, 按日期)
# ═══════════════════════════════════════════════

GITHUB_QUERIES = [
    ("python algorithms", "programming"),
    ("machine learning implementation", "ai"),
    ("distributed system example", "systems"),
    ("math library python", "math"),
    ("quantitative finance python", "finance"),
]

PAPER_STATUSES = ["raw", "comprehended", "hypothesized", "verified", "integrated"]


class ExternalFetcher:
    """统一外部知识下载器。"""

    def __init__(self):
        EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
        (EXTERNAL_DIR / "papers").mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    # ═══════════════════════════════════════════
    # 调度
    # ═══════════════════════════════════════════

    def should_fetch(self) -> bool:
        now = datetime.now()
        if now.hour < 2 or now.hour >= 6:
            return False
        last = self._state.get("last_fetch_ts", 0)
        if time.time() - last < 23 * 3600:
            return False
        offset = self._state.get("fetch_offset", random.randint(-1800, 1800))
        if "fetch_offset" not in self._state:
            self._state["fetch_offset"] = offset
            self._save_state()
        return True

    def fetch_all(self) -> Dict:
        result = {"papers": 0, "code": 0, "finance": 0, "math": 0}

        result["papers"] = self._fetch_papers()
        result["code"] = self._fetch_github()
        result["finance"] = self._fetch_akshare()
        result["math"] = self._fetch_python_math()

        self._state["last_fetch_ts"] = time.time()
        self._save_state()

        if sum(result.values()) > 0:
            logger.info("[ExternalFetcher] papers=%d code=%d finance=%d math=%d",
                       result["papers"], result["code"], result["finance"], result["math"])
        return result

    # ═══════════════════════════════════════════
    # 1. arXiv 论文 (独立目录, 学术研究专用)
    # ═══════════════════════════════════════════

    def _fetch_papers(self, per_domain: int = 15) -> int:
        papers_dir = EXTERNAL_DIR / "papers"
        date_str = datetime.now().strftime("%Y-%m-%d")
        cache_file = papers_dir / f"{date_str}.json"

        existing = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else []
        existing_ids = {p["arxiv_id"] for p in existing}
        existing_ids.update(self._state.get("paper_ids", set()))

        new_papers = []
        for domain, keywords in PAPER_DOMAINS.items():
            for kw in keywords[:2]:
                try:
                    papers = self._search_arxiv(kw, max_results=per_domain // 2)
                    for p in papers:
                        if p["arxiv_id"] not in existing_ids:
                            p["domain"] = domain
                            p["status"] = "raw"
                            p["fetched_at"] = time.time()
                            new_papers.append(p)
                            existing_ids.add(p["arxiv_id"])
                except Exception:
                    logger.debug("[ExternalFetcher] arXiv %s/%s failed", domain, kw)

        if new_papers:
            all_papers = existing + new_papers
            cache_file.write_text(json.dumps(all_papers, ensure_ascii=False, indent=2), encoding="utf-8")
            self._state["paper_ids"] = list(existing_ids)[-8000:]

        # 15天清理
        self._cleanup_papers(days=15)

        return len(new_papers)

    def get_paper_inventory(self, status: str = "raw", domain: str = None, limit: int = 50) -> List[Dict]:
        papers_dir = EXTERNAL_DIR / "papers"
        papers = []
        for f in sorted(papers_dir.glob("*.json"), reverse=True):
            try:
                for p in json.loads(f.read_text(encoding="utf-8")):
                    if status and p.get("status") != status:
                        continue
                    if domain and p.get("domain") != domain:
                        continue
                    papers.append(p)
            except Exception:
                pass
        return papers[:limit]

    def update_paper_status(self, arxiv_id: str, new_status: str):
        if new_status not in PAPER_STATUSES:
            return
        papers_dir = EXTERNAL_DIR / "papers"
        for f in sorted(papers_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for p in data:
                    if p.get("arxiv_id") == arxiv_id:
                        p["status"] = new_status
                        p["status_updated"] = time.time()
                        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        return
            except Exception:
                pass

    def _cleanup_papers(self, days: int = 15):
        papers_dir = EXTERNAL_DIR / "papers"
        cutoff = time.time() - days * 86400
        total = 0
        for f in sorted(papers_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                kept = []
                for p in data:
                    if p.get("status") == "integrated" and p.get("status_updated", 0) > 0 and p.get("status_updated", 0) < cutoff:
                        total += 1
                        continue
                    kept.append(p)
                if total > 0:
                    f.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        if total > 0:
            logger.info("[ExternalFetcher] Cleaned %d integrated papers", total)

    # ═══════════════════════════════════════════
    # 2. GitHub 代码 (日期文件夹, 研究完立即删)
    # ═══════════════════════════════════════════

    def _fetch_github(self) -> int:
        date_str = datetime.now().strftime("%Y-%m-%d")
        code_dir = EXTERNAL_DIR / "code" / date_str
        code_dir.mkdir(parents=True, exist_ok=True)

        fetched_repos = self._state.get("github_fetched", set())
        downloaded = 0

        for query, domain in GITHUB_QUERIES:
            try:
                url = (f"https://api.github.com/search/repositories?"
                       f"q={urllib.request.quote(query)}&sort=stars&per_page=5")
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA, "Accept": "application/vnd.github.v3+json"})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                    data = json.loads(r.read())
                    for item in data.get("items", [])[:3]:
                        full_name = item["full_name"]
                        if full_name in fetched_repos:
                            continue
                        # 存 repo 摘要 + 下载链接
                        info = {
                            "full_name": full_name,
                            "description": item.get("description", ""),
                            "url": item["html_url"],
                            "stars": item.get("stargazers_count", 0),
                            "language": item.get("language", ""),
                            "domain": domain,
                            "fetched_at": time.time(),
                            "status": "raw",
                        }
                        meta_file = code_dir / f"{full_name.replace('/', '_')}.json"
                        meta_file.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
                        fetched_repos.add(full_name)
                        downloaded += 1
            except Exception:
                logger.debug("[ExternalFetcher] GitHub %s failed", query)

        self._state["github_fetched"] = list(fetched_repos)[-3000:]
        return downloaded

    def get_code_inventory(self, date_str: str = None, limit: int = 50) -> List[Dict]:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        code_dir = EXTERNAL_DIR / "code" / date_str
        if not code_dir.exists():
            return []
        items = []
        for f in code_dir.glob("*.json"):
            try:
                items.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return items[:limit]

    def mark_code_studied(self, date_str: str, filename: str):
        """SelfPlay研究完 → 立即删除 + 记录去重。"""
        code_dir = EXTERNAL_DIR / "code" / date_str
        f = code_dir / filename
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                studied = self._state.get("code_studied", [])
                studied.append({
                    "full_name": data.get("full_name", ""),
                    "studied_at": time.time(),
                })
                self._state["code_studied"] = studied[-2000:]
                f.unlink()
            except Exception:
                logger.debug("code cleanup failed", exc_info=True)

    # ═══════════════════════════════════════════
    # 3. akshare 金融数据
    # ═══════════════════════════════════════════

    def _fetch_akshare(self) -> int:
        date_str = datetime.now().strftime("%Y-%m-%d")
        fin_dir = EXTERNAL_DIR / "finance" / date_str
        fin_dir.mkdir(parents=True, exist_ok=True)

        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
                sample = df.head(50).to_dict(orient="records")
                out = {
                    "date": date_str,
                    "source": "akshare",
                    "total_stocks": len(df),
                    "sample": sample,
                    "columns": list(df.columns),
                }
                f = fin_dir / "a_stock_spot.json"
                f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                return 1
        except ImportError:
            logger.debug("[ExternalFetcher] akshare not installed")
        except Exception:
            logger.debug("[ExternalFetcher] akshare fetch failed")
        return 0

    def get_finance_inventory(self, date_str: str = None) -> List[Dict]:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        fin_dir = EXTERNAL_DIR / "finance" / date_str
        if not fin_dir.exists():
            return []
        items = []
        for f in fin_dir.glob("*.json"):
            try:
                items.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return items

    # ═══════════════════════════════════════════
    # 4. Python 官方数学文档
    # ═══════════════════════════════════════════

    def _fetch_python_math(self) -> int:
        date_str = datetime.now().strftime("%Y-%m-%d")
        math_dir = EXTERNAL_DIR / "math" / date_str
        math_dir.mkdir(parents=True, exist_ok=True)

        sources = {
            "math": "https://raw.githubusercontent.com/python/cpython/main/Doc/library/math.rst",
            "statistics": "https://raw.githubusercontent.com/python/cpython/main/Doc/library/statistics.rst",
            "itertools": "https://raw.githubusercontent.com/python/cpython/main/Doc/library/itertools.rst",
        }
        downloaded = 0
        for name, url in sources.items():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=15) as r:
                    content = r.read().decode("utf-8", errors="replace")
                    out = {"source": "python_docs", "module": name,
                           "fetched_at": time.time(), "content": content[:5000]}
                    f = math_dir / f"{name}.json"
                    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                    downloaded += 1
            except Exception:
                logger.debug("[ExternalFetcher] python %s failed", name)
        return downloaded

    def get_math_inventory(self, date_str: str = None) -> List[Dict]:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        math_dir = EXTERNAL_DIR / "math" / date_str
        if not math_dir.exists():
            return []
        items = []
        for f in math_dir.glob("*.json"):
            try:
                items.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return items

    # ═══════════════════════════════════════════
    # arXiv API
    # ═══════════════════════════════════════════

    def _search_arxiv(self, query: str, max_results: int = 10) -> List[Dict]:
        encoded = urllib.parse.quote(query)
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance"
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
                papers.append({
                    "arxiv_id": aid,
                    "title": " ".join(entry.find("atom:title", ns).text.split()),
                    "authors": [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)][:5],
                    "abstract": " ".join(entry.find("atom:summary", ns).text.split()),
                    "published": entry.find("atom:published", ns).text[:10],
                    "categories": [c.get("term") for c in entry.findall("atom:category", ns)],
                    "content_hash": hashlib.md5((entry.find("atom:title", ns).text + entry.find("atom:summary", ns).text[:200]).encode()).hexdigest()[:16],
                })
            except Exception:
                continue
        return papers

    # ═══════════════════════════════════════════
    # State
    # ═══════════════════════════════════════════

    def _load_state(self) -> Dict:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                for k in ("paper_ids", "github_fetched", "code_studied"):
                    if k in data and isinstance(data[k], list):
                        data[k] = set(data[k])
                return data
            except Exception:
                pass
        return {"paper_ids": set(), "github_fetched": set(), "code_studied": []}

    def _save_state(self):
        data = {}
        for k, v in self._state.items():
            if isinstance(v, set):
                data[k] = list(v)[-5000:]
            else:
                data[k] = v
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── Singleton ─────────────────────────────────────────────

_fetcher: Optional[ExternalFetcher] = None


def get_external_fetcher() -> ExternalFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = ExternalFetcher()
    return _fetcher
