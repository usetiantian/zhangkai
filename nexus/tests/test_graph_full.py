"""测试: 图引擎 + 社区检测 + 多Agent编排"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge.graph_engine import GraphEngine
from knowledge.community import CommunityDetector
from knowledge.orchestrator import PlanExecuteReportOrchestrator
from knowledge.rag_engine import RAGEngine

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

# === 图引擎 ===
kg = GraphEngine()
kg.add_entity("zhangkai", "张凯", "person")
kg.add_entity("nexus", "Nexus", "project")
kg.add_entity("stock", "股票分析", "skill")
kg.add_entity("cad", "CAD画图", "skill")
kg.add_relation("zhangkai", "nexus", "founded")
kg.add_relation("zhangkai", "stock", "uses")
kg.add_relation("zhangkai", "cad", "uses")
check("图引擎:节点", kg.stats()["nodes"] == 4)
check("图引擎:边", kg.stats()["edges"] == 3)

# === 社区检测 ===
cd = CommunityDetector()
comms = cd.detect(kg.nodes, kg.edges)
check("社区检测:分组", len(comms) >= 1)
# 张凯和所有东西应该在同一社区
for nids in comms.values():
    if "zhangkai" in nids:
        check("社区检测:张凯关联", "nexus" in nids or "stock" in nids)

# === RAG引擎 ===
rag = RAGEngine()
rag.ingest_document("Nexus是张凯的AI平台，支持股票分析和CAD画图", "doc1")
check("RAG:摄入", rag.stats()["docs"] == 1)

# === 多Agent编排 ===
orch = PlanExecuteReportOrchestrator()
tools = [
    {"name": "search", "description": "搜索知识库"},
    {"name": "graph", "description": "查询知识图谱"},
    {"name": "rag", "description": "检索文档"},
]
plan = orch.create_plan("张凯的Nexus项目有哪些技能", tools)
check("编排:规划", len(plan) >= 2)

# 模拟执行
def mock_executor(step):
    if step["action"] == "search":
        return kg.search(step["target"])
    elif step["action"] == "retrieve":
        return rag.search(step["target"])
    return []

for step in plan:
    orch.execute_step(step, mock_executor)

report = orch.generate_report()
check("编排:执行", report["completed"] >= 1)
check("编排:报告", report["verdict"] in ("complete", "partial"))

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
