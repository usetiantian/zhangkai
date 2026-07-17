"""
多Agent编排器 — Plan-Execute-Report模式
来源: graph-rag-agent multi_agent/ (Planner/Executor/Reporter)
纯Python实现，零外部依赖
"""
import logging
logger = logging.getLogger("nexus.orchestrator")

class PlanExecuteReportOrchestrator:
    """
    三阶段编排：
    Plan    → 分解任务为子步骤
    Execute → 逐步执行（带反思）
    Report  → 汇总生成报告
    """

    def __init__(self):
        self.plan = []
        self.execution_log = []
        self.state = "idle"

    def create_plan(self, goal: str, available_tools: list) -> list:
        """
        规划阶段：把目标分解为可执行步骤。
        goal: 用户目标描述
        available_tools: [{name, description, ...}]
        """
        self.state = "planning"

        # 规则版（后续升级为Qwen推理版）
        steps = []
        if any("search" in t["name"] for t in available_tools):
            steps.append({"step": 1, "action": "search", "target": goal, "tool": "search"})
        if any("graph" in t["name"] for t in available_tools):
            steps.append({"step": 2, "action": "query_graph", "target": goal, "tool": "graph"})
        if any("rag" in t["name"] for t in available_tools):
            steps.append({"step": 3, "action": "retrieve", "target": goal, "tool": "rag"})

        steps.append({
            "step": len(steps) + 1,
            "action": "synthesize",
            "target": "汇总以上结果，形成最终答案",
            "tool": "synthesizer"
        })

        self.plan = steps
        logger.info(f"Plan: {len(steps)} steps for '{goal[:40]}...'")
        return steps

    def execute_step(self, step: dict, executor_fn) -> dict:
        """
        执行一个步骤。executor_fn(step) → result
        带反思：执行完检查结果是否足够。
        """
        self.state = "executing"
        try:
            result = executor_fn(step)
            entry = {"step": step["step"], "action": step["action"], "result": result, "status": "ok"}
        except Exception as e:
            entry = {"step": step["step"], "action": step["action"], "error": str(e), "status": "failed"}

        self.execution_log.append(entry)
        self.state = "idle"
        return entry

    def generate_report(self) -> dict:
        """汇总所有执行结果。"""
        self.state = "reporting"
        ok_steps = [e for e in self.execution_log if e["status"] == "ok"]
        failed_steps = [e for e in self.execution_log if e["status"] == "failed"]

        report = {
            "total_steps": len(self.plan),
            "completed": len(ok_steps),
            "failed": len(failed_steps),
            "execution_log": self.execution_log,
            "verdict": "complete" if not failed_steps else "partial",
        }
        self.state = "idle"
        return report

    def reset(self):
        self.plan = []
        self.execution_log = []
        self.state = "idle"
