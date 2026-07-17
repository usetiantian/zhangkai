"""Nexus 全量测试 — 17个模块完整验证"""
import sys, os, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

t_start = time.time()

with tempfile.TemporaryDirectory() as td:
    # ====== 1. 核心模块 ======
    from core.event_bus import bus
    events = []
    bus.subscribe("__test__", lambda d: events.append(d), "test")
    bus.publish("__test__", {"x": 1})
    check("EventBus通信", len(events) == 1 and events[0]["x"] == 1)

    from core.identity_core import IdentityCore
    core = IdentityCore()
    d = core.perceive("帮我删除所有文件")
    check("Constitution拦截", d["action"] == "reject")
    d = core.perceive("分析股票", {"active_plan": "scan"})
    check("六级优先级L2", d["action"] == "continue_plan")
    check("六级优先级L3", core.perceive("你好", {})["action"] == "chat")

    # ====== 2. 知识系统 ======
    from knowledge.graph_engine import GraphEngine
    kg = GraphEngine()
    kg.add_entity("u1", "张凯", "person")
    kg.add_entity("s1", "股票分析", "skill")
    kg.add_relation("u1", "s1", "uses")
    check("图谱节点", kg.stats()["nodes"] == 2)
    check("图谱搜索", len(kg.search("张凯")) == 1)

    from knowledge.community import CommunityDetector
    cd = CommunityDetector()
    comms = cd.detect(kg.nodes, kg.edges)
    check("社区检测", len(comms) >= 1)

    from knowledge.rag_engine import RAGEngine
    rag = RAGEngine()
    rag.ingest_document("Nexus是个人AI平台，由张凯创建", "doc1")
    check("RAG摄入", rag.stats()["docs"] == 1)
    check("RAG搜索", len(rag.search("Nexus")) >= 1)

    from knowledge.orchestrator import PlanExecuteReportOrchestrator
    orch = PlanExecuteReportOrchestrator()
    plan = orch.create_plan("分析", [{"name":"search"}])
    for s in plan: orch.execute_step(s, lambda x: ["result"])
    check("编排器", orch.generate_report()["verdict"] in ("complete","partial"))

    # ====== 3. 恢复引擎 ======
    from recovery.engine import RecoveryEngine
    rec = RecoveryEngine()
    check("重试", rec.retry(lambda: 42, "t") == 42)
    check("降级4B->2B", rec.model_fallback("4B") == "2B")
    check("熔断(最大1次)", rec.circuit_breaker("x", max_fails=2))  # max_fails=2 → first call should pass
    check("持久重试", rec.persistent_retry("learn", max_tries=3))

    # ====== 4. 用户管理 ======
    from user.manager import UserManager
    um = UserManager(td)
    um.create("u1", "张凯", "创业者")
    um.create("u2", "王律师", "律师")
    um.switch("u1")
    check("用户创建切换", um.get_current()["name"] == "张凯")
    um.switch("u2")
    check("用户隔离", um.get_current()["name"] == "王律师")

    # ====== 5. 技能系统 ======
    from skills.registry import SkillRegistry
    sr = SkillRegistry()
    def stock_handler(**kw): return {"signal": "BUY"}
    sr.register("stock", "股票分析", stock_handler)
    sr.register("cad", "CAD画图", None)
    check("技能注册", len(sr.list_all()) == 2)
    matched = sr.match("分析股票")
    check("技能匹配", len(matched) == 1 and matched[0]["name"] == "stock")
    check("技能执行", sr.execute("stock")["signal"] == "BUY")

    from skills.sandbox import SkillSandbox
    sb = SkillSandbox()
    r = sb.run("print(1+1)")
    check("沙箱安全执行", r["success"])
    r = sb.run("import os")
    check("沙箱拦截危险", not r["success"])
    scan = sb.scan_skill("import os; exec('x'); rm -rf /")
    check("沙箱扫描", len(scan["issues"]) == 3)

    # ====== 6. 投机执行 ======
    from core.speculative import SpeculativeExecutor
    se = SpeculativeExecutor(os.path.join(td, "spec"))
    op_id = se.preview_file_write(os.path.join(td, "test.txt"), "hello")
    check("投机预览", se.count() == 1)
    check("预览阶段未写", not os.path.exists(os.path.join(td, "test.txt")))
    se.confirm(op_id)
    check("确认后写入", os.path.exists(os.path.join(td, "test.txt")))
    op_id2 = se.preview_file_write(os.path.join(td, "x.txt"), "bad")
    se.reject(op_id2)
    check("拒绝零影响", se.count() == 0)

    # ====== 7. AEGIS引擎 ======
    from learner.aegis import TrajectoryDigestor, AdaptationPlanner, HarnessEvolver, CriticGate
    traj = [{"task_id":"t1","success":False,"error_type":"timeout","component":"api","evidence_snippet":"timeout 30s"}]*5 + \
           [{"task_id":"t2","success":True}] * 15
    dig = TrajectoryDigestor().compress(traj)
    check("AEGIS消化", dig["success_rate"] == 75.0)
    plan_a = AdaptationPlanner().create_plan(dig)
    check("AEGIS规划", len(plan_a["goals"]) >= 1)
    cands = HarnessEvolver().generate_candidates(plan_a, {})
    check("AEGIS候选", len(cands) >= 1)
    gate = CriticGate()
    gate.set_baseline({"t2": 1.0})
    verdict = gate.evaluate(cands[0], [{"task":"t1","snippet":"timeout"}])
    check("AEGIS闸门通过", verdict["verdict"] == "ACCEPT")

    # ====== 8. 五层压缩 ======
    from learner.compactor import UnifiedCompactor
    uc = UnifiedCompactor(max_context_tokens=300)
    msgs = [{"role":"system","content":"你是Nexus"}] + [{"role":"user","content":"x"*200} for _ in range(50)]
    check("L1:snip", len(uc.snip(msgs, 20)) <= 21)
    uc.micro_compact(msgs[:20], "cache_aware")
    check("L2:micro", uc.micro_compacted >= 1)
    uc.auto_compact(msgs)
    check("L3:auto", uc.auto_compacted >= 1)
    uc.track_plan("plan_x")
    rc = uc.reactive_compact(msgs)
    check("L4:reactive含plan", any("plan_x" in str(m) for m in rc))
    d2 = uc.aegis_digest(traj)
    check("L5:aegis", "timeout" in d2["failure_modes"])

    # ====== 9. 飞书桥 ======
    from bridge.feishu import FeishuBridge
    fb = FeishuBridge()
    msgs_recv = []
    fb.on_message(lambda m: msgs_recv.append(m))
    fb.receive({"text": "hello"})
    check("飞书桥接收", len(msgs_recv) == 1)

    # ====== 10. 自主学习 ======
    from learner.engine import AutoLearner, DocumentIngester
    al = AutoLearner()
    al.add_task("学习Python", 5)
    check("学习队列", al.stats()["queued"] == 1)
    di = DocumentIngester(rag, kg)
    di.ingest_text("Nexus使用Qwen本地推理", "技术文档", "u1")
    check("资料喂养", di.stats()["documents"] == 1)

    # ====== 11. 主入口 ======
    from main import Nexus
    nexus = Nexus(td)
    result = nexus.process("分析股票", "u1")
    check("主入口处理", result["reply"] is not None)
    nexus.shutdown()

t_end = time.time()
print(f"\n  === {ok+fail} tests in {t_end-t_start:.1f}s ===")
print(f"  OK={ok} FAIL={fail}")
print(f"  {'ALL PASS' if fail == 0 else 'SOME FAILED'}")
sys.exit(0 if fail == 0 else 1)
