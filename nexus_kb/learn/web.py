"""
网络搜索/爬虫 — 知识库自主上网找资料

搜索后端:
  1. DuckDuckGo (免费，无需 API key)
  2. configurable web search API

网页内容提取:
  - 纯文本提取（去除 HTML 标签）
  - 自动摄入搜索结果到知识库

用途:
  - 用户问"搜一下XX最新进展" → 自动搜索→抓取→摄入
  - 知识空白检测 → 自动生成搜索词→抓取→摄入
"""

import urllib.request, urllib.parse, json, re, logging

logger = logging.getLogger("nexus_kb.web")


class WebSearcher:
    """网络搜索引擎。"""

    def __init__(self):
        self.results_cache = {}

    def search(self, query: str, max_results: int = 5) -> list:
        """
        搜索网络。先尝试 DuckDuckGo，失败则返回空。
        返回: [{"title": ..., "url": ..., "snippet": ...}, ...]
        """
        results = []
        try:
            results = self._search_duckduckgo(query, max_results)
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
        return results

    def _search_duckduckgo(self, query: str, max_results: int = 5) -> list:
        """DuckDuckGo HTML 搜索（无需 API key）。"""
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="replace")

        # 简单正则提取结果
        results = []
        # 找结果块
        blocks = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>', html)
        snippets = re.findall(r'<a class="result__snippet"[^>]*>([^<]+)</a>', html)

        for i, (url, title) in enumerate(blocks[:max_results]):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append({
                "title": self._clean_html(title),
                "url": self._clean_url(url),
                "snippet": self._clean_html(snippet),
            })

        return results

    def _clean_html(self, text: str) -> str:
        return re.sub(r'<[^>]+>', '', text).strip()

    def _clean_url(self, url: str) -> str:
        # DuckDuckGo wraps URLs, extract real one
        if "//duckduckgo.com/l/" in url:
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            uddg = qs.get("uddg", [url])[0]
            return urllib.parse.unquote(uddg)
        return url


class WebCrawler:
    """网页内容抓取器。"""

    def fetch(self, url: str, timeout: int = 10) -> dict:
        """
        抓取网页纯文本内容。
        返回: {"url": ..., "title": ..., "text": ..., "chars": ...}
        """
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", errors="replace")
            text = self._extract_text(html)
            title = self._extract_title(html) or url
            return {"url": url, "title": title, "text": text[:5000], "chars": len(text)}
        except Exception as e:
            logger.warning(f"Fetch failed for {url}: {e}")
            return {"url": url, "error": str(e)}

    def _extract_title(self, html: str) -> str:
        m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        return self._strip_tags(m.group(1)) if m else ""

    def _extract_text(self, html: str) -> str:
        # 去掉 script/style
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # 去掉 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', html)
        # 去掉多余空白
        text = re.sub(r'\s+', ' ', text)
        # 去掉 HTML 实体
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&#39;", "'")
        return text.strip()

    def _strip_tags(self, text: str) -> str:
        return re.sub(r'<[^>]+>', '', text).strip()


class WebKnowledgeBridge:
    """网络搜索 + 知识库桥接。"""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.searcher = WebSearcher()
        self.crawler = WebCrawler()

    def search_and_ingest(self, query: str, max_results: int = 3, max_fetch: int = 2) -> dict:
        """
        搜索网络 → 抓取内容 → 摄入知识库。
        返回: {"query": ..., "searched": N, "fetched": N, "ingested": N}
        """
        results = self.searcher.search(query, max_results)
        if not results:
            return {"query": query, "searched": 0, "fetched": 0, "ingested": 0}

        ingested = 0
        for r in results[:max_fetch]:
            content = self.crawler.fetch(r["url"])
            if content.get("error"):
                continue
            text = f"Title: {content['title']}\nURL: {content['url']}\n\n{content['text']}"
            source = f"web:{r['title'][:50]}"
            self.kb.ingest_text(text, source)
            ingested += 1

        return {"query": query, "searched": len(results), "fetched": max_fetch, "ingested": ingested}

    def search_only(self, query: str, max_results: int = 5) -> list:
        """只搜索不摄入。"""
        return self.searcher.search(query, max_results)
