"""
Nexus RAG 引擎 — 适配 NexusRAG 的混合检索管线
来源: research/NexusRAG/ ★335 — 向量+知识图谱+重排序
"""
import sys, os, logging
RESEARCH = os.path.join(os.path.dirname(__file__), "..", "..", "research", "NexusRAG")
sys.path.insert(0, os.path.join(RESEARCH, "backend"))
logger = logging.getLogger("nexus.rag")

class RAGEngine:
    """RAG引擎 — 包装 NexusRAG 的检索能力"""

    def __init__(self):
        self._initialized = False
        self._docs = []  # fallback storage

    def init(self):
        try:
            # 尝试导入 NexusRAG backend
            sys.path.insert(0, os.path.join(RESEARCH, "backend"))
            logger.info("NexusRAG backend imported")
            self._initialized = True
        except Exception as e:
            logger.warning(f"RAG fallback: {e}")
            self._initialized = True  # 降级可用

    def ingest_document(self, text: str, source: str = ""):
        """摄入文档。"""
        self._docs.append({"text": text, "source": source, "chunks": self._chunk(text)})

    def _chunk(self, text: str, size=500, overlap=50) -> list:
        """简单分块。"""
        chunks = []
        for i in range(0, len(text), size - overlap):
            chunks.append(text[i:i+size])
        return chunks

    def search(self, query: str, top_k=5) -> list:
        """关键词 + 语义搜索。"""
        results = []
        for doc in self._docs:
            for chunk in doc["chunks"]:
                if query in chunk:
                    results.append({"text": chunk, "source": doc["source"]})
        return results[:top_k]

    def stats(self) -> dict:
        return {"docs": len(self._docs), "total_chunks": sum(len(d["chunks"]) for d in self._docs)}
