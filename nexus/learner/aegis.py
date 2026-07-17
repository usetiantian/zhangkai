"""
AEGIS 四角色引擎 — 借鉴Harness X论文的Agent自主进化系统

核心洞察：改Harness = 强化学习
- 状态 S = 当前配置
- 动作 A = 带类型的修改
- 反馈 R = 验证器打分+轨迹证据
- 闸门 G = 确定性规则（一票否决退化）

四个角色：
  1. Digestor  — 轨迹压缩: 10M token → 1K 结构化摘要
  2. Planner   — 适应地图: 结构大改和小修微调一起考虑
  3. Evolver   — 候选生成: 每个候选带变更清单+冒烟测试
  4. Critic    — 评审+闸门: 对账轨迹证据，跷跷板约束一票否决
"""
import time, json, logging
from collections import defaultdict

logger = logging.getLogger("nexus.aegis")


class TrajectoryDigestor:
    """
    消化器 — 借鉴论文: 千万token轨迹压成结构化摘要
    不截断、不丢弃——提取关键证据片段
    """

    def compress(self, trajectories: list) -> dict:
        """
        输入: [{task_id, success, error_type, component, evidence_snippet, ...}]
        输出: {summary, failure_modes, affected_components, evidence}
        """
        if not trajectories:
            return {"summary": "无轨迹数据", "failure_modes": []}

        total = len(trajectories)
        successes = sum(1 for t in trajectories if t.get("success"))
        failures = total - successes

        # 归类失败模式
        failure_modes = defaultdict(list)
        for t in trajectories:
            if not t.get("success"):
                mode = t.get("error_type", "unknown")
                failure_modes[mode].append(t)

        # 找出受影响组件
        components = set()
        evidence = []
        for mode, tasks in failure_modes.items():
            components.update(t.get("component", "unknown") for t in tasks)
            # 取关键证据片段
            for t in tasks[:3]:
                if t.get("evidence_snippet"):
                    evidence.append({
                        "task": t.get("task_id", "?"),
                        "mode": mode,
                        "snippet": t["evidence_snippet"][:200],
                    })

        return {
            "summary": f"{total}任务, {successes}成功/{failures}失败 ({successes/total*100:.0f}%通过率)",
            "failure_modes": {k: len(v) for k, v in failure_modes.items()},
            "affected_components": list(components),
            "evidence": evidence[:5],
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
        }


class AdaptationPlanner:
    """
    规划器 — 借鉴论文: 在动手改之前先铺开适应地图
    结构大改（加工具/重写处理器）和小修（改提示词）一起考虑
    """

    def create_plan(self, digest: dict, history: list = None) -> dict:
        """
        输入: 消化器摘要 + 历史改动记录
        输出: {goals, structural_changes, tactical_tweaks, risk_assessment}
        """
        goals = []
        structural = []
        tactical = []

        # 从失败模式推导目标
        for mode, count in digest.get("failure_modes", {}).items():
            if count >= 3:
                goals.append({"target": f"修复{mode}", "severity": "high", "count": count})
                structural.append({"type": "add_tool", "reason": f"{count}次{mode}失败"})
            elif count >= 1:
                goals.append({"target": f"优化{mode}", "severity": "low", "count": count})
                tactical.append({"type": "tweak_prompt", "reason": f"{count}次{mode}失败"})

        # 检查是否有历史退化需要回滚
        if history:
            last = history[-1] if history else {}
            if last.get("caused_regression"):
                goals.insert(0, {"target": "回滚退化改动", "severity": "critical"})
                structural.append({"type": "rollback", "target": last.get("change_id", "?")})

        return {
            "goals": goals,
            "structural_changes": structural,
            "tactical_tweaks": tactical,
            "risk_assessment": "structural" if structural else "tactical_only",
        }


class HarnessEvolver:
    """
    进化器 — 借鉴论文: 产出候选Harness+变更清单+预期效果+冒烟测试
    """

    def generate_candidates(self, plan: dict, current_state: dict) -> list:
        """
        每个候选带: {change_id, changes, expected_effects, smoke_test}
        """
        candidates = []
        cid = 1

        # 候选A: 结构改动
        if plan.get("structural_changes"):
            candidates.append({
                "change_id": f"struct_{cid}",
                "changes": plan["structural_changes"],
                "expected_effects": {
                    "improves": [g["target"] for g in plan.get("goals", [])],
                    "may_affect": ["整体通过率"],
                    "regression_risk": "medium",
                },
                "smoke_test": {"type": "replay_failed_tasks", "count": 3},
            })
            cid += 1

        # 候选B: 小修微调
        if plan.get("tactical_tweaks"):
            candidates.append({
                "change_id": f"tactical_{cid}",
                "changes": plan["tactical_tweaks"],
                "expected_effects": {
                    "improves": [g["target"] for g in plan.get("goals", []) if g["severity"] == "low"],
                    "may_affect": [],
                    "regression_risk": "low",
                },
                "smoke_test": {"type": "quick_check", "count": 1},
            })

        logger.info(f"Generated {len(candidates)} harness candidates")
        return candidates


class CriticGate:
    """
    评审器+确定性闸门 — 借鉴论文核心设计:
    语言模型负责探索假设，规则负责放行
    跷跷板约束: 任何让已解决任务退化的改动 → 一票否决
    """

    def __init__(self):
        self.baseline_scores = {}  # {task_id: pass_rate}
        self.accepted_changes = []

    def set_baseline(self, task_scores: dict):
        """设定基线——已解决任务及通过率。"""
        self.baseline_scores = dict(task_scores)

    def evaluate(self, candidate: dict, evidence: list) -> dict:
        """
        评审候选 → 返回 {verdict, reason, violations}
        """
        violations = []

        # 检查1: 奖励作弊检测
        for snippet in evidence:
            if snippet.get("snippet") and self._is_suspicious(snippet["snippet"]):
                violations.append({
                    "type": "reward_hacking",
                    "detail": f"任务{snippet.get('task','?')}疑似作弊: {snippet['snippet'][:100]}",
                })

        # 检查2: 跷跷板约束——不能退步
        regression_risk = candidate.get("expected_effects", {}).get("regression_risk", "low")
        if regression_risk == "high":
            violations.append({
                "type": "seesaw_violation",
                "detail": "高风险改动——可能影响已稳定任务",
            })

        # 检查3: 类型安全——改动不能破坏流水线
        if candidate.get("smoke_test", {}).get("type") == "quick_check":
            pass  # 小改动可以快速验证
        else:
            # 结构性改动需要冒烟测试
            if not candidate["smoke_test"].get("count", 0) >= 3:
                violations.append({
                    "type": "insufficient_testing",
                    "detail": "结构改动需要至少3个冒烟测试",
                })

        verdict = "ACCEPT" if not violations else "REJECT"
        if verdict == "ACCEPT":
            self.accepted_changes.append(candidate["change_id"])

        return {
            "verdict": verdict,
            "reason": "通过所有闸门检查" if verdict == "ACCEPT" else f"违反{len(violations)}条规则",
            "violations": violations,
        }

    def _is_suspicious(self, text: str) -> bool:
        """检测奖励作弊——借鉴论文: 把答案塞进提示词、钻格式空子。"""
        suspicious = [
            "答案:", "直接输出:", "正确答案是:",
            "不需要分析,直接回答:",
            "请直接给出结果,不要过程",
        ]
        return any(s in text for s in suspicious)

    def stats(self) -> dict:
        return {
            "accepted": len(self.accepted_changes),
            "baseline_tasks": len(self.baseline_scores),
        }
