"""
Nexus 知识图谱引擎 — 纯 Python，零外部依赖

设计借鉴：graph-rag-agent 的社区检测+多Agent编排模式
实现：自己写的纯Python图（无Neo4j依赖）
"""
import json, os, logging
logger = logging.getLogger("nexus.knowledge")

class GraphEngine:
    """纯Python知识图谱。借鉴graph-rag-agent的架构设计。"""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: set[tuple] = set()
        self.name_index: dict[str, set[str]] = {}
        self._communities = []

    def add_entity(self, nid: str, name: str, entity_type: str = "entity", **props):
        """添加实体节点。"""
        self.nodes[nid] = {"name": name, "type": entity_type, **props}
        self.name_index.setdefault(name, set()).add(nid)

    def add_relation(self, from_id: str, to_id: str, relation: str):
        """添加关系边。"""
        for nid in [from_id, to_id]:
            if nid not in self.nodes:
                self.add_entity(nid, nid)
        self.edges.add((from_id, to_id, relation))

    def get_neighbors(self, node_id: str, relation: str = None, direction: str = "both") -> list:
        """查邻居（借鉴图遍历模式）。"""
        results = []
        for f, t, r in self.edges:
            if direction in ("out", "both") and f == node_id and (relation is None or r == relation):
                results.append({"node": self.nodes.get(t, {}), "relation": r, "direction": "out"})
            if direction in ("in", "both") and t == node_id and (relation is None or r == relation):
                results.append({"node": self.nodes.get(f, {}), "relation": r, "direction": "in"})
        return results

    def search(self, keyword: str, top_k: int = 10) -> list:
        """关键词搜索。"""
        results = []
        for name, ids in self.name_index.items():
            if keyword in name:
                for nid in ids:
                    if nid in self.nodes:
                        results.append(self.nodes[nid])
        return results[:top_k]

    def stats(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "communities": len(self._communities),
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "nodes": self.nodes,
                "edges": [list(e) for e in self.edges],
                "name_index": {k: list(v) for k, v in self.name_index.items()}
            }, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "GraphEngine":
        kg = cls()
        if not os.path.exists(path): return kg
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        kg.nodes = d.get("nodes", {})
        kg.edges = {tuple(e) for e in d.get("edges", [])}
        kg.name_index = {k: set(v) for k, v in d.get("name_index", {}).items()}
        return kg
