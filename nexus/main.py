"""
Nexus 主入口 — 启动所有模块，进入主循环
用法: python main.py
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("nexus")

from core.event_bus import bus
from core.identity_core import IdentityCore
from knowledge.graph_engine import GraphEngine
from knowledge.rag_engine import RAGEngine
from knowledge.community import CommunityDetector
from knowledge.orchestrator import PlanExecuteReportOrchestrator
from recovery.engine import RecoveryEngine
from user.manager import UserManager
from skills.registry import SkillRegistry
from learner.engine import AutoLearner, DocumentIngester

class Nexus:
    """Nexus — 个人AI操作系统"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(self.data_dir, exist_ok=True)

        # 初始化所有模块
        self.identity = IdentityCore()
        self.graph = GraphEngine()
        self.rag = RAGEngine()
        self.community = CommunityDetector()
        self.orchestrator = PlanExecuteReportOrchestrator()
        self.recovery = RecoveryEngine()
        self.users = UserManager(self.data_dir)
        self.skills = SkillRegistry()
        self.learner = AutoLearner()
        self.ingester = DocumentIngester(self.rag, self.graph)

        # 加载 Constitution
        constitution_path = os.path.join(os.path.dirname(__file__), "..", ".claude", "constitution.md")
        if os.path.exists(constitution_path):
            self.identity.load_constitution(constitution_path)

        # 连接 EventBus
        self._wire_bus()
        logger.info("Nexus initialized")

    def _wire_bus(self):
        """模块间通过 EventBus 通信 — 14条连接。"""
        nexus = self  # 闭包引用

        # 1. 用户输入 → 身份核心感知
        bus.subscribe("user.message", lambda d: nexus.identity.perceive(d.get("text","")), "identity_core")

        # 2. 用户输入 → 图谱记录用户实体
        bus.subscribe("user.message", lambda d: nexus.graph.add_entity(
            d.get("user","unknown"), d.get("user",""), "user"), "graph")

        # 3. 用户输入 → 短期记忆追加
        bus.subscribe("user.message", lambda d: nexus.rag.ingest_document(
            f"[{d.get('user','?')}] {d.get('text','')}", f"memory:{d.get('user','')}"), "rag")

        # 4. 身份核心决策 → 编排器执行
        bus.subscribe("identity.decision", lambda d: nexus._exec_decision(d), "orchestrator")

        # 5. 模块死亡 → 恢复引擎处理
        bus.subscribe("module.dead", lambda d: logger.warning(f"Module {d.get('module','?')} DEAD — recovery needed"), "monitor")

        # 6. 错误发生 → 恢复引擎记录
        bus.subscribe("error.occurred", lambda d: nexus.recovery.circuit_breaker(
            d.get("module","unknown")), "recovery")

        # 7. 文档摄入 → 图谱建关系
        bus.subscribe("document.ingested", lambda d: nexus.graph.add_relation(
            d.get("owner",""), d.get("source",""), "owns"), "graph")

        # 8. 学习需求 → 自主学习引擎
        bus.subscribe("learning.needed", lambda d: nexus.learner.add_task(
            d.get("topic",""), d.get("priority",3)), "learner")

        # 9. 容器状态查询
        bus.subscribe("nexus.status", lambda _: None, "status")

        bus.module_alive("nexus")
        logger.info("EventBus wired: 9 connections")

    def _exec_decision(self, decision: dict):
        """执行身份核心的调度决策。"""
        action = decision.get("action", "chat")
        target = decision.get("target", "qwen")
        if action == "analyze":
            self.orchestrator.create_plan(decision.get("reason", ""), [{"name": "search"}, {"name": "graph"}])
        elif action == "learn":
            self.learner.add_task(decision.get("reason", ""), decision.get("priority", 3))

    def process(self, user_input: str, user_id: str = "default") -> dict:
        """处理用户输入。"""
        # 自动创建用户
        user_path = os.path.join(self.users.data_dir, f"{user_id}.json")
        if not os.path.exists(user_path):
            self.users.create(user_id, user_id)
        self.users.switch(user_id)

        # 身份核心分析意图
        decision = self.identity.perceive(user_input)
        if decision["action"] == "reject":
            return {"reply": f"操作被拒绝: {decision['reason']}", "action": "reject"}

        # 编排器执行
        tools = [{"name": "search"}, {"name": "graph"}, {"name": "rag"}]
        plan = self.orchestrator.create_plan(user_input, tools)
        for step in plan:
            self.orchestrator.execute_step(step, lambda s: self.rag.search(s["target"]))

        report = self.orchestrator.generate_report()
        return {"reply": f"处理完成: {report['completed']}/{report['total_steps']}步", "action": decision["action"]}

    def status(self) -> dict:
        return {
            "graph": self.graph.stats(),
            "rag": self.rag.stats(),
            "learner": self.learner.stats(),
            "ingester": self.ingester.stats(),
            "users": {"current": self.users.current},
            "skills": len(self.skills.list_all()),
        }

    def shutdown(self):
        self.graph.save(os.path.join(self.data_dir, "graph.json"))
        logger.info("Nexus shutdown complete")


if __name__ == "__main__":
    nexus = Nexus()
    print(f"Nexus ready. Status: {nexus.status()}")
    print("Enter 'quit' to exit.")
    while True:
        try:
            text = input("\n> ")
            if text.lower() in ("quit", "exit"): break
            result = nexus.process(text)
            print(f"  [{result['action']}] {result['reply']}")
        except KeyboardInterrupt:
            break
    nexus.shutdown()
