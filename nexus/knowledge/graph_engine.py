"""
Nexus 知识图谱引擎
适配自: research/graph-rag-agent/graphrag_agent/
来源: graph-rag-agent ★2275 — 社区检测+混合搜索+多Agent编排
"""
import sys, os, logging
# 引用研究库代码
RESEARCH = os.path.join(os.path.dirname(__file__), "..", "..", "research", "graph-rag-agent")
sys.path.insert(0, RESEARCH)

logger = logging.getLogger("nexus.knowledge")

class GraphEngine:
    """知识图谱引擎 — 包装 graph-rag-agent 的图能力"""

    def __init__(self):
        self._graph = None
        self._initialized = False

    def init_graph(self, working_dir: str):
        """初始化图结构。"""
        try:
            from graphrag_agent.graph.structure import GraphStructure
            self._graph = GraphStructure()
            self._initialized = True
            logger.info(f"Graph engine initialized (graph-rag-agent)")
        except Exception as e:
            logger.warning(f"Graph init fallback: {e}")
            # 降级：用纯Python图
            from .simple_graph import SimpleGraph
            self._graph = SimpleGraph()
            self._initialized = True

    def add_entity(self, name: str, entity_type: str, properties: dict = None):
        if not self._initialized:
            self.init_graph(".")
        # 用简单接口包装
        if hasattr(self._graph, 'add_node'):
            self._graph.add_node(name, name, entity_type, **(properties or {}))

    def add_relation(self, from_entity: str, to_entity: str, relation: str):
        if hasattr(self._graph, 'add_edge'):
            self._graph.add_edge(from_entity, to_entity, relation)

    def query(self, text: str, top_k: int = 5) -> list:
        """语义搜索 + 图谱检索。"""
        if hasattr(self._graph, 'search'):
            return self._graph.search(text)[:top_k]
        return []

    def community_detect(self):
        """社区检测 — Leiden 算法（如果可用）。"""
        if hasattr(self._graph, 'community_detection'):
            return self._graph.community_detection()
        return []

    def stats(self) -> dict:
        if hasattr(self._graph, 'stats'):
            return self._graph.stats()
        return {"status": "not_initialized"}
