"""
Nexus KnowledgeGraph — 纯Python，零外部依赖
替代Neo4j。dict+set存节点和边。
"""
import json, os, logging
logger = logging.getLogger("nexus.graph")

class KnowledgeGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: set[tuple] = set()
        self.index: dict[str, set[str]] = {}

    def add_node(self, nid: str, name: str, ntype: str = "entity", **props):
        if nid in self.nodes:
            self.nodes[nid].update(props)
        else:
            self.nodes[nid] = {"name": name, "type": ntype, **props}
        self.index.setdefault(name, set()).add(nid)

    def get_node(self, nid: str) -> dict:
        return self.nodes.get(nid, {})

    def find_by_name(self, name: str) -> list:
        return [self.nodes[nid] for nid in self.index.get(name, set()) if nid in self.nodes]

    def search(self, kw: str) -> list:
        return [self.nodes[nid] for name, ids in self.index.items()
                if kw in name for nid in ids if nid in self.nodes]

    def add_edge(self, frm: str, to: str, rel: str):
        self.edges.add((frm, to, rel))
        for nid in [frm, to]:
            if nid not in self.nodes:
                self.add_node(nid, nid)

    def get_neighbors(self, nid: str, rel: str = None, direction: str = "out") -> list:
        results = []
        for f, t, r in self.edges:
            if direction in ("out","both") and f == nid and (rel is None or r == rel):
                results.append({"node": self.nodes.get(t,{}), "relation": r})
            if direction in ("in","both") and t == nid and (rel is None or r == rel):
                results.append({"node": self.nodes.get(f,{}), "relation": r})
        return results

    def stats(self) -> dict:
        return {"nodes": len(self.nodes), "edges": len(self.edges)}

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "nodes": self.nodes,
                "edges": [list(e) for e in self.edges],
                "index": {k: list(v) for k, v in self.index.items()}
            }, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "KnowledgeGraph":
        kg = cls()
        if not os.path.exists(path): return kg
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        kg.nodes = d.get("nodes", {})
        kg.edges = {tuple(e) for e in d.get("edges", [])}
        kg.index = {k: set(v) for k, v in d.get("index", {}).items()}
        return kg
