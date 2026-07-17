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
from memory.context import ConversationContext
from core.proactive import ProactiveEngine
from core.autonomous import AutonomousAgent
from core.prompts import PromptBuilder, build_quick_prompt
from core.heartbeat import HeartbeatLoop
from core.state_awareness import StateAwareness
from core.user_cognition import UserCognition
from core.onboarding import Onboarding

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
        self.context = ConversationContext()
        self.proactive = ProactiveEngine()
        self.autonomous = AutonomousAgent()
        self.heartbeat = HeartbeatLoop(self.data_dir)
        self.state = StateAwareness()
        self.user_cog = UserCognition(os.path.join(self.data_dir, "users"))
        self.heartbeat.boot()
        # Auto-load Qwen (takes 12s, only on first start)
        self._loader = None
        try:
            from models.loader import ModelLoader
            self._loader = ModelLoader()
            print('  [Qwen] Loading...', end='', flush=True)
            self._loader.load()
            self.identity.attach_model(lambda p, mt=64: self._loader.generate(p, max_tokens=mt))
            print(' ready')
        except Exception as e:
            print(f'  [Qwen] Skipped: {e}')

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
        """处理用户输入——带上下文记忆。"""
        # 自动创建用户
        user_path = os.path.join(self.users.data_dir, f"{user_id}.json")
        if not os.path.exists(user_path):
            self.users.create(user_id, user_id)
        self.users.switch(user_id)

        # 注入对话上下文到身份核心
        ctx_summary = self.context.get_context(user_id)
        decision = self.identity.perceive(user_input, {"conversation_history": ctx_summary})
        if decision["action"] == "reject":
            return {"reply": f"操作被拒绝: {decision['reason']}", "action": "reject"}

        # 编排器执行
        tools = [{"name": "search"}, {"name": "graph"}, {"name": "rag"}]
        plan = self.orchestrator.create_plan(user_input, tools)
        for step in plan:
            self.orchestrator.execute_step(step, lambda s: self.rag.search(s["target"]))

        report = self.orchestrator.generate_report()

        # 用Qwen生成自然回复(带上下文)
        reply = self._generate_reply(user_input, decision, report, user_id)

        # 记录对话到上下文
        self.context.add(user_id, "user", user_input)
        self.context.add(user_id, "nexus", reply)

        # 主动引擎观察+思考+建议
        self.proactive.observe(user_id, decision["action"])
        self.state.interaction_count += 1
        self.state.last_interaction = __import__("time").time()
        self.user_cog.observe(user_id, decision["action"])
        suggestions = self.proactive.think(user_id, decision["action"])
        hint = ""
        if suggestions and self.proactive.should_suggest(user_id):
            hint = f"\n[主动建议] {suggestions[0]['suggestion']}"

        # 每5轮对话后，自主引擎心跳一次
        ctx_stats = self.context.stats(user_id)
        if ctx_stats["turns"] % 5 == 0:
            self.autonomous.tick(self)

        return {"reply": reply + hint, "action": decision["action"]}

    def _generate_reply(self, user_input: str, decision: dict, report: dict, user_id: str = "default") -> str:
        """用Qwen生成自然回复。不可用时降级为规则回复。"""
        action = decision["action"]
        if action == "reject":
            return f"[拒绝] {decision['reason']}"

        # 获取对话上下文
        conv_ctx = self.context.get_context(user_id)

        # 尝试Qwen
        try:
            prompt = self._build_prompt(user_input, decision, report, conv_ctx)
            if len(prompt) < 50:
                return self._fallback_reply(action, report)
            if self._loader is not None and self._loader.model:
                return self._loader.generate(prompt, max_tokens=100)
        except Exception:
            pass

        if self._loader is not None:
            from core.prompts import build_quick_prompt
            qp = build_quick_prompt(user_input, action)
            try:
                raw = self._loader.generate(qp, max_tokens=50)
                # Qwen有时返回prompt原文 → 过滤掉
                if len(raw) > 10 and "你是Nexus" not in raw[:20] and raw != qp:
                    return raw.strip()
            except: pass
        return self._fallback_reply(action, report)

    def _build_prompt(self, user_input: str, decision: dict, report: dict, conv_ctx: str = "") -> str:
        """构建Qwen推理prompt——借鉴ClaudeCode模块化+静态动态分离。"""
        action = decision["action"]
        info = self.rag.search(user_input)
        knowledge = "\n".join([r["text"][:200] for r in info[:2]]) if info else ""

        # 用PromptBuilder(借鉴ClaudeCode)替代原来硬编码的模板
        builder = PromptBuilder(
            soul_path=os.path.join(os.path.dirname(__file__), "..", ".claude", "SOUL.md"),
            constitution_path=os.path.join(os.path.dirname(__file__), "..", ".claude", "constitution.md")
        )
        user_ctx = self.user_cog.get_context(user_id)
        full_ctx = user_ctx + "
" + conv_ctx if conv_ctx else user_ctx
        state_snap = self.state.snapshot()
        if state_snap["description"] != "正常":
            full_ctx += "
" + state_snap["description"]
        return builder.build(action, full_ctx, knowledge)

    def _fallback_reply(self, action: str, report: dict) -> str:
        replies = {
            "analyze": "已分析。建议结合RSI和量比综合判断。",
            "learn": "已加入学习队列，稍后为你整理资料。",
            "skill": "Nexus支持这个功能。",
            "chat": "你好！有什么可以帮你的？",
        }
        return replies.get(action, f"处理完成({report['completed']}步)")

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
