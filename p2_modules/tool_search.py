# -*- coding: utf-8 -*-
"""Semantic tool discovery — embedding-based search over tool registry (Cursor/Windsurf-style)."""
import hashlib, logging, re, time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

@dataclass
class ToolDescriptor:
    name: str; description: str; category: str; tags: List[str]=field(default_factory=list)
    usage_count: int=0; success_rate: float=0.5; last_used: float=0.0
    embedding: Optional[List[float]]=None  # Lazily computed

@dataclass
class SearchResult:
    tool: ToolDescriptor; score: float; match_reason: str

class ToolSearchEngine:
    """Progressive tool disclosure with semantic search."""

    CORE_TOOLS = ["read","write","edit","bash","grep","glob"]
    DEFAULT_TOOLS = {
        "read": ToolDescriptor("read","Read file contents","file",["read","view","cat","open"]),
        "write": ToolDescriptor("write","Write/create file","file",["write","create","save","new"]),
        "edit": ToolDescriptor("edit","Edit file in-place","file",["edit","modify","change","update","patch"]),
        "bash": ToolDescriptor("bash","Execute shell command","system",["bash","shell","run","exec","cmd"]),
        "grep": ToolDescriptor("grep","Search file contents","search",["grep","search","find","lookup"]),
        "glob": ToolDescriptor("glob","Find files by pattern","search",["glob","find","ls","dir","list"]),
        "web_search": ToolDescriptor("web_search","Search the internet","web",["web","search","google","internet"]),
        "web_fetch": ToolDescriptor("web_fetch","Fetch webpage content","web",["web","fetch","url","download","scrape"]),
        "task": ToolDescriptor("task","Run sub-agent task","agent",["task","agent","delegate","subagent"]),
        "memory_search": ToolDescriptor("memory_search","Search knowledge base","memory",["memory","knowledge","recall","remember"]),
    }

    def __init__(self):
        self._tools: Dict[str, ToolDescriptor] = dict(self.DEFAULT_TOOLS)
        self._lru: OrderedDict = OrderedDict()  # LRU cache for search results
        self._MAX_LRU = 100
        self._embedding_cache: Dict[str, List[float]] = {}

    def register(self, name: str, description: str, category: str, tags: List[str] = None):
        self._tools[name] = ToolDescriptor(name=name, description=description, category=category, tags=tags or [])
        self._lru.clear()  # Invalidate cache
        logger.debug("[ToolSearch] Registered: %s", name)

    def search(self, query: str, top_k: int = 5, prefer_recent: bool = True) -> List[SearchResult]:
        """Semantic search for tools matching a natural language query."""
        cache_key = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        if cache_key in self._lru:
            self._lru.move_to_end(cache_key)
            return self._lru[cache_key]

        query_lower = query.lower()
        results = []

        for name, tool in self._tools.items():
            score = self._score_tool(tool, query_lower)

            # Recency boost
            if prefer_recent and tool.last_used > 0:
                recency_boost = min(0.15, 1.0 / (1.0 + time.time() - tool.last_used) * 0.1)
                score += recency_boost

            # Success rate boost
            score += tool.success_rate * 0.1

            if score > 0.05:
                reason = self._explain_match(tool, query_lower)
                results.append(SearchResult(tool=tool, score=round(min(score, 1.0), 3), match_reason=reason))

        results.sort(key=lambda x: -x.score)
        top = results[:top_k]

        # Always include core tools
        core_included = set(r.tool.name for r in top)
        for ct in self.CORE_TOOLS:
            if ct not in core_included and ct in self._tools:
                top.append(SearchResult(tool=self._tools[ct], score=0.01, match_reason="core_tool"))

        self._lru[cache_key] = top
        if len(self._lru) > self._MAX_LRU:
            self._lru.popitem(last=False)

        return top

    def _score_tool(self, tool: ToolDescriptor, query: str) -> float:
        score = 0.0
        name_lower = tool.name.lower()
        desc_lower = tool.description.lower()

        # Exact name match
        if query == name_lower:
            return 1.0
        if query in name_lower:
            score += 0.8
        elif name_lower in query:
            score += 0.6

        # Word overlap in name
        query_words = set(query.split())
        name_words = set(name_lower.replace("_"," ").split())
        overlap = query_words & name_words
        score += len(overlap) * 0.15

        # Tag matching
        for tag in tool.tags:
            if tag in query:
                score += 0.2
                break

        # Description matching
        desc_words = set(desc_lower.split())
        desc_overlap = query_words & desc_words
        score += len(desc_overlap) * 0.05

        # Category affinity
        category_keywords = {
            "file": ["file","read","write","edit","create","delete","open","save"],
            "search": ["search","find","look","grep","glob","ls","list","where"],
            "web": ["web","url","http","internet","browser","download","fetch","page"],
            "system": ["shell","bash","run","exec","command","terminal","cmd","process"],
            "memory": ["memory","remember","recall","knowledge","know","learn","store"],
            "agent": ["agent","task","delegate","sub","do","work","help"],
        }
        for cat, kws in category_keywords.items():
            if tool.category == cat:
                cat_overlap = query_words & set(kws)
                score += len(cat_overlap) * 0.05

        return min(score, 0.99)

    def _explain_match(self, tool: ToolDescriptor, query: str) -> str:
        reasons = []
        if query in tool.name.lower():
            reasons.append("name_match")
        if any(tag in query for tag in tool.tags):
            reasons.append("tag_match")
        query_words = set(query.split())
        desc_words = set(tool.description.lower().split())
        if query_words & desc_words:
            reasons.append("description_match")
        return ",".join(reasons) if reasons else "loose_match"

    def record_usage(self, name: str, success: bool = True):
        if name in self._tools:
            tool = self._tools[name]
            tool.usage_count += 1
            tool.last_used = time.time()
            tool.success_rate = (tool.success_rate * (tool.usage_count - 1) + (1.0 if success else 0.0)) / tool.usage_count

    def describe(self, name: str) -> Optional[Dict]:
        tool = self._tools.get(name)
        if not tool: return None
        return {"name":tool.name,"description":tool.description,"category":tool.category,
                "tags":tool.tags,"usage_count":tool.usage_count,"success_rate":tool.success_rate}

    def list_all(self, category: str = None) -> List[Dict]:
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.category == category]
        return [self.describe(t.name) for t in tools]

    def get_stats(self) -> Dict:
        total_usage = sum(t.usage_count for t in self._tools.values())
        return {"tools_registered":len(self._tools),"total_usage":total_usage,
                "most_used":sorted(self._tools.values(),key=lambda t:-t.usage_count)[:5]}


_engine: Optional[ToolSearchEngine] = None
def get_tool_search() -> ToolSearchEngine:
    global _engine
    if _engine is None: _engine = ToolSearchEngine()
    return _engine
