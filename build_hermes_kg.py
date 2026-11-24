"""Build hermes-kg __init__.py without bash escaping hell"""
import os

TARGET = r"C:\Users\87999\AppData\Local\hermes\plugins\hermes-kg\__init__.py"

# Write the source file directly
with open(TARGET, "w", encoding="utf-8") as f:
    f.write('''"""Hermes-KG — Knowledge Graph + Experience Bank Memory Provider

8-step closed loop:
  1. prefetch()        — Before turn: KG search + experience FTS recall
  2. system_prompt()   — Tell model about KG/experience capabilities
  3. sync_turn()       — After turn: auto-record experience + extract KG entities
  4. queue_prefetch()  — Background: preload recall for next turn
  5. on_memory_write() — Mirror MEMORY.md writes to KG nodes
  6. on_pre_compress() — Extract knowledge before context compression
  7. on_session_end()  — Deep extraction from full conversation
  8. handle_tool_call()— Model actively queries KG/experiences

4-dimension KG: concept | person | project | tool
5-step experience: record -> auto_score -> recall -> format -> inject
"""

import json, threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider


class HermesKGProvider(MemoryProvider):
    """KG + Experience Bank provider for Hermes Agent"""

    def __init__(self):
        self._db_path = ""
        self._session_id = ""
        self._turn = 0
        self._prefetched = ""
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "hermes-kg"

    def is_available(self) -> bool:
        return bool(self._db_path)

    def initialize(self, session_id: str, **kwargs) -> None:
        hermes_home = kwargs.get("hermes_home", "~/.hermes")
        self._db_path = str(Path(hermes_home) / "hermes-kg.db")
        self._session_id = session_id
        from . import db
        db.init(self._db_path)
        conn = db.get_db()
        conn.execute(
            "INSERT OR REPLACE INTO sessions_meta (session_id, first_seen) "
            "VALUES (?, datetime('now','localtime'))",
            (session_id,))
        conn.commit()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "kg_search",
                "description": "Search knowledge graph for concepts, people, projects, tools and their relationships.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keywords"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "exp_recall",
                "description": "Recall past conversation experiences from the experience bank. Use when unsure how to handle a situation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keywords"},
                        "domain": {"type": "string", "description": "Optional domain filter"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "kg_stats",
                "description": "View knowledge graph and experience bank statistics",
                "parameters": {"type": "object", "properties": {}},
            },
        ]

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        with self._lock:
            if self._prefetched:
                result = self._prefetched
                self._prefetched = ""
                return result
        return self._do_recall(query)

    def system_prompt_block(self) -> str:
        try:
            from . import kg, experience
            kg_s = kg.stats()
            exp_s = experience.get_stats()
            return (
                "## Your Memory System\\n"
                f"Knowledge Graph: {kg_s['nodes']} nodes, {kg_s['edges']} relations. "
                f"Experience Bank: {exp_s['total']} experiences ({exp_s['good_ratio']:.0%} positive).\\n"
                "Use kg_search / exp_recall tools to query your memory. "
                "Experiences are auto-saved after each turn.\\n"
            )
        except Exception:
            return ""

    def sync_turn(self, user_content: str, assistant_content: str, *,
                  session_id: str = "", messages=None) -> None:
        self._turn += 1
        sid = session_id or self._session_id
        tools_used = []
        if messages:
            for m in messages:
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    for tc in m["tool_calls"]:
                        if isinstance(tc, dict):
                            tools_used.append(tc.get("function", {}).get("name", ""))
        try:
            from . import experience
            domain = _classify_domain(user_content)
            experience.record(sid, self._turn, user_content, assistant_content, tools_used, domain)
        except Exception:
            pass
        try:
            from . import kg
            combined = user_content + " " + assistant_content
            for entity_name, entity_type in kg.extract_facts(combined):
                kg.add_node(entity_name, entity_type)
            for tool in tools_used:
                kg.relate("hermes", tool, "uses")
        except Exception:
            pass
        try:
            from . import db
            conn = db.get_db()
            conn.execute(
                "UPDATE sessions_meta SET turn_count=?, last_seen=datetime('now','localtime') WHERE session_id=?",
                (self._turn, sid))
            conn.commit()
        except Exception:
            pass

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        def _bg():
            result = self._do_recall(query)
            with self._lock:
                self._prefetched = result
        threading.Thread(target=_bg, daemon=True).start()

    def on_memory_write(self, action: str, target: str, content: str, metadata=None) -> None:
        if action == "add" and content:
            try:
                from . import kg
                name = content.split("\n")[0][:60].strip()
                if name:
                    kg.add_node(name, "concept", source=target, content=content[:200])
            except Exception:
                pass

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        facts = []
        try:
            from . import kg
            for m in messages:
                c = m.get("content", "")
                if isinstance(c, str) and len(c) > 20:
                    for f in kg.extract_facts(c):
                        facts.append(f)
        except Exception:
            pass
        if not facts:
            return ""
        seen = set()
        lines = ["[Knowledge extracted before compression]"]
        for name, ntype in facts:
            if name not in seen:
                seen.add(name)
                lines.append(f"  {name} ({ntype})")
        return "\n".join(lines)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not messages:
            return
        try:
            from . import kg
            all_text = " ".join(
                m.get("content", "") for m in messages
                if isinstance(m.get("content"), str)
            )[:5000]
            facts = kg.extract_facts(all_text)
            for name, ntype in facts:
                kg.add_node(name, ntype)
            fact_names = [f[0] for f in facts[:20]]
            for i in range(len(fact_names)):
                for j in range(i + 1, min(i + 5, len(fact_names))):
                    kg.relate(fact_names[i], fact_names[j],
                              "co_occurred_in_session",
                              weight=0.3,
                              evidence=f"session_{self._session_id}")
        except Exception:
            pass

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        try:
            if tool_name == "kg_search":
                from . import kg
                return json.dumps(kg.search(args.get("query", "")), ensure_ascii=False, default=str)
            elif tool_name == "exp_recall":
                from . import experience
                query = args.get("query", "")
                domain = args.get("domain")
                exps = experience.recall_by_domain(domain) if domain else experience.recall(query)
                return experience.format_recall(exps)
            elif tool_name == "kg_stats":
                from . import kg, experience
                return json.dumps({
                    "kg": kg.stats(),
                    "experience": experience.get_stats(),
                    "session_turns": self._turn,
                }, ensure_ascii=False)
            return json.dumps({"error": f"unknown tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _do_recall(self, query: str) -> str:
        parts = []
        try:
            from . import kg, experience
            kg_ctx = kg.inject_context(query)
            if kg_ctx:
                parts.append(kg_ctx)
            exps = experience.recall(query)
            exp_ctx = experience.format_recall(exps)
            if exp_ctx:
                parts.append(exp_ctx)
        except Exception:
            pass
        return "\n".join(parts) if parts else ""


def _classify_domain(text: str) -> str:
    t = text.lower()
    for kw in ["code", "def ", "class ", "import ", "bug", "error"]:
        if kw in t:
            return "code"
    for kw in ["stock", "a股", "股票", "k线"]:
        if kw in t:
            return "stock"
    for kw in ["search", "搜索", "查"]:
        if kw in t:
            return "search"
    return "chat"


def register(ctx):
    ctx.register_memory_provider(HermesKGProvider())
''')

print(f"Written {os.path.getsize(TARGET)} bytes to {TARGET}")
