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

    def search(self, query: str, top_k: int = 10) -> list:
        """子串匹配节点名——不需要模型，速度快。"""
        if not self.nodes: return []
        q = query.lower()
        scored = []
        for name, nids in self.name_index.items():
            if q in name.lower():
                scored.append((len(name), name, nids))
        scored.sort()  # 短名字优先（更精确匹配）
        results = []
        seen = set()
        for _, name, nids in scored:
            for nid in nids:
                if nid not in seen and nid in self.nodes:
                    seen.add(nid)
                    results.append(self.nodes[nid])
                    if len(results) >= top_k:
                        return results
        return results

    def remove_entity(self, nid: str):
        """删除节点及其所有关联边。"""
        if nid in self.nodes:
            name = self.nodes[nid].get("name", nid)
            self.nodes.pop(nid)
            if name in self.name_index:
                self.name_index[name].discard(nid)
                if not self.name_index[name]:
                    del self.name_index[name]
        self.edges = {(f, t, r) for f, t, r in self.edges if f != nid and t != nid}

    def remove_relation(self, from_id: str, to_id: str, relation: str):
        """删除一条关系边。"""
        self.edges.discard((from_id, to_id, relation))

    def stats(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "communities": len(self._communities),
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "nodes": self.nodes,
                "edges": [list(e) for e in self.edges],
                "name_index": {k: list(v) for k, v in self.name_index.items()}
            }, f, ensure_ascii=False)
        os.replace(tmp, path)  # 原子替换

    @classmethod
    def load(cls, path: str) -> "GraphEngine":
        kg = cls()
        if not os.path.exists(path): return kg
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            kg.nodes = d.get("nodes", {})
            kg.edges = {tuple(e) for e in d.get("edges", [])}
            kg.name_index = {k: set(v) for k, v in d.get("name_index", {}).items()}
        except Exception:
            pass  # 损坏就空图重来
        return kg
