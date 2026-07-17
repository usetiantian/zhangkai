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
        """模块间通过 EventBus 通信。"""
        bus.subscribe("user.message", lambda d: self.graph.add_entity(d.get("user","unknown"), d.get("user",""), "user"), "graph")
        bus.subscribe("user.message", lambda d: self.identity.perceive(d.get("text","")), "identity")
        bus.module_alive("nexus")

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
