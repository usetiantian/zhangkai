"""Nexus 全模块综合测试"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge.graph_engine import GraphEngine
from knowledge.rag_engine import RAGEngine
from knowledge.community import CommunityDetector
from knowledge.orchestrator import PlanExecuteReportOrchestrator
from recovery.engine import RecoveryEngine
from user.manager import UserManager

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

with tempfile.TemporaryDirectory() as td:
    # 1. 图引擎+社区检测
    kg = GraphEngine()
    for name in ["张凯","Nexus","股票分析","CAD画图","法律咨询"]:
        kg.add_entity(name, name, "entity")
    kg.add_relation("张凯","Nexus","founded")
    kg.add_relation("张凯","股票分析","uses")
    kg.add_relation("张凯","CAD画图","uses")

    cd = CommunityDetector()
    comms = cd.detect(kg.nodes, kg.edges)
    check("图+社区", len(comms) >= 1)

    # 2. RAG
    rag = RAGEngine()
    rag.ingest_document("Nexus是张凯的个人AI平台，支持多技能扩展", "立项书")
    check("RAG搜索", len(rag.search("Nexus")) >= 1)

    # 3. 编排器
    orch = PlanExecuteReportOrchestrator()
    tools = [{"name":"search"}, {"name":"graph"}, {"name":"rag"}]
    plan = orch.create_plan("Nexus有什么功能", tools)
    for step in plan:
        orch.execute_step(step, lambda s: ["result"])
    report = orch.generate_report()
    check("编排完整", report["verdict"] in ("complete","partial"))
    check("编排步骤", report["total_steps"] >= 2)

    # 4. 恢复引擎
    rec = RecoveryEngine()
    result = rec.retry(lambda: 42, "test")
    check("重试成功", result == 42)
    check("模型降级", rec.model_fallback("4B") == "2B")
    check("熔断器初始", rec.circuit_breaker("api"))

    # 5. 用户管理
    um = UserManager(td)
    um.create("u1", "张凯", "创业者")
    um.create("u2", "王律师", "律师")
    um.switch("u1")
    check("用户创建+切换", um.get_current()["name"] == "张凯")
    um.switch("u2")
    check("用户隔离", um.get_current()["name"] == "王律师")

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
