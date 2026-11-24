"""
DocumentIngester — 从 nexus/learner/engine.py 抽取
将文档文本摄入 RAG + 知识图谱
"""

import logging
logger = logging.getLogger("nexus_kb.ingest")


class DocumentIngester:
    """个人资料喂养——PDF/Word/PPT/图片OCR"""

    def __init__(self, rag_engine, graph_engine):
        self.rag = rag_engine
        self.graph = graph_engine
        self.ingested = []

    def ingest_text(self, text: str, source: str, owner: str = "default"):
        self.rag.ingest_document(text, source)
        self.graph.add_entity(source, source, "document", owner=owner, size=len(text))
        self.graph.add_relation(owner, source, "owns")
        self.ingested.append({"source": source, "size": len(text), "owner": owner})
        logger.info(f"Ingested: {source} ({len(text)} chars)")

    def stats(self) -> dict:
        return {"documents": len(self.ingested), "total_chars": sum(d["size"] for d in self.ingested)}
