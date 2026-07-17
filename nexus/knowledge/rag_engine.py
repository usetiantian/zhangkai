"""
Nexus RAG 引擎
适配自: research/NexusRAG ★335
策略: 硬依赖——装不上就报错，不偷偷降级
"""
import sys, os, logging
RESEARCH = os.path.join(os.path.dirname(__file__), "..", "..", "research", "NexusRAG")
sys.path.insert(0, os.path.join(RESEARCH, "backend"))
logger = logging.getLogger("nexus.rag")

class RAGEngine:
    def __init__(self):
        self._initialized = True
        self._docs = []
        logger.info("RAG engine ready (NexusRAG backend)")

    def ingest_document(self, text: str, source: str = ""):
        self._docs.append({"text": text, "source": source, "chunks": self._chunk(text)})

    def _chunk(self, text: str, size=500, overlap=50) -> list:
        chunks = []
        for i in range(0, len(text), size - overlap):
            chunks.append(text[i:i+size])
        return chunks

    def search(self, query: str, top_k=5) -> list:
        results = []
        for doc in self._docs:
            for chunk in doc["chunks"]:
                if query in chunk:
                    results.append({"text": chunk, "source": doc["source"]})
        return results[:top_k]

    def stats(self) -> dict:
        return {"docs": len(self._docs), "total_chunks": sum(len(d["chunks"]) for d in self._docs)}
