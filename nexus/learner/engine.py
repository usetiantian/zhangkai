"""自主学习引擎——借鉴ClaudeCode autoDream + GrokBuild dream蒸馏"""
import os, logging
logger = logging.getLogger("nexus.learner")

class AutoLearner:
    """后台自主学习——发现不足→搜索→消化→微调"""
    def __init__(self):
        self.learning_queue = []
        self.completed = []

    def add_task(self, topic: str, priority: int = 3):
        self.learning_queue.append({"topic": topic, "priority": priority, "status": "pending"})

    def process(self, rag_engine, graph_engine) -> list:
        """处理学习队列。"""
        results = []
        for task in sorted(self.learning_queue, key=lambda x: x["priority"], reverse=True):
            if task["status"] == "pending":
                # 从RAG搜索现有知识
                existing = rag_engine.search(task["topic"])
                if existing:
                    task["status"] = "found_in_rag"
                else:
                    task["status"] = "need_external_search"
                results.append(task)
        return results

    def stats(self) -> dict:
        return {"queued": len(self.learning_queue), "completed": len(self.completed)}


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
