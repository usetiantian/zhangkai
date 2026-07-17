"""Pure Python fallback graph — when graph-rag-agent can't be imported"""
class SimpleGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = set()
    def add_node(self, nid, name, ntype="entity", **props):
        self.nodes[nid] = {"name": name, "type": ntype, **props}
    def add_edge(self, frm, to, rel):
        self.edges.add((frm, to, rel))
    def search(self, kw):
        return [n for n in self.nodes.values() if kw in n.get("name","")]
    def stats(self):
        return {"nodes": len(self.nodes), "edges": len(self.edges)}
