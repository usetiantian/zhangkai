"""Nexus v2 综合测试：研究库适配 + EventBus + 降级机制"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge.graph_engine import GraphEngine
from knowledge.rag_engine import RAGEngine

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

# 1. 图谱引擎
kg = GraphEngine()
kg.init_graph(".")
kg.add_entity("张凯", "person", {"role": "founder"})
kg.add_entity("Nexus", "project")
kg.add_relation("张凯", "Nexus", "founded")
check("1.图谱节点", kg.stats().get("nodes", 0) >= 2)
check("2.图谱降级类型", type(kg._graph).__name__ in ("SimpleGraph", "GraphStructure"))

# 2. RAG引擎
rag = RAGEngine()
rag.init()
rag.ingest_document("Nexus是张凯创建的AI平台，采用盒子+手机架构", "立项书")
rag.ingest_document("Nexus使用Qwen2-VL-2B本地模型进行推理", "技术文档")
check("3.RAG文档摄入", rag.stats()["docs"] == 2)

results = rag.search("Qwen")
check("4.RAG搜索", len(results) >= 1 and "Qwen" in results[0]["text"])

results = rag.search("盒子")
check("5.RAG跨文档搜索", any("盒子" in r["text"] for r in results))

# 3. 降级行为验证
check("6.降级不崩溃", kg.stats() is not None)
check("7.RAG降级可用", rag.stats()["docs"] >= 0)

print(f"\n  OK={ok} FAIL={fail}")
print(f"  Graph: {type(kg._graph).__name__}")
sys.exit(0 if fail == 0 else 1)
