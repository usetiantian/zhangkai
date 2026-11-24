"""Goal Tracker v2 — grok-build 深度实现: token核算 + 指纹检测 + 策略师 + 基准计划"""

import json, uuid, re, time, hashlib
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path


class GoalStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    PAUSED = "paused"
    ACHIEVED = "achieved"
    FAILED = "failed"


class GoalPhase(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"


@dataclass
class GoalOrchestration:
    """grok-build GoalOrchestration 的 Python 实现"""

    # 身份
    goal_id: str = ""
    objective: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    phase: GoalPhase = GoalPhase.PLANNING
    created_at: str = ""

    # Token 核算
    token_budget: int | None = None
    token_baseline: int = 0          # 目标创建时的 token 总量
    tokens_used_high_water: int = 0  # 高水位
    parent_tokens_spent: int = 0     # 累计花费
    last_session_tokens_seen: int | None = None  # 上次快照

    # 时间
    elapsed_ms: int = 0
    total_worker_rounds: int = 0
    total_verify_rounds: int = 0

    # 验证
    classifier_runs_attempted: int = 0
    classifier_max_runs: int | None = None
    last_classifier_verdict: str | None = None  # Achieved / NotAchieved
    rounds_since_verify: int = 0

    # 缺口指纹 — 检测卡在同一问题上
    last_gap_fingerprint: str | None = None
    classifier_stall_count: int = 0
    consecutive_not_achieved: int = 0
    last_strategist_fired_at: int = 0
    strategist_cap_bonus: int = 0

    # 基准计划 — 对比原始计划 vs 当前状态
    plan_file: str | None = None
    plan_baseline: str | None = None  # 原始计划快照

    # 历史
    history: list = field(default_factory=list)

    # 实时指标 (不持久化)
    live_subagent_tokens: int = 0
    live_context_window: int = 0
    live_context_pct: int = 0
    live_turn_count: int = 0
    live_tool_call_count: int = 0

    # 飞行的子 Agent
    current_subagent_id: str | None = None
    current_subagent_role: str | None = None
    planning_in_flight: bool = False
    verifying_in_flight: bool = False

    def __post_init__(self):
        if not self.goal_id:
            self.goal_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    def record_token_spend(self, current_total: int):
        """记录 token 花费 (参照 grok-build 的差分累积)"""
        if self.last_session_tokens_seen is None:
            self.last_session_tokens_seen = current_total
            return
        delta = current_total - self.last_session_tokens_seen
        if delta > 0:
            self.parent_tokens_spent += delta
        self.tokens_used_high_water = max(
            self.tokens_used_high_water, current_total)
        self.last_session_tokens_seen = current_total

    def fingerprint_gaps(self, gaps: list[str]) -> str:
        """缺口指纹 — 用于检测重复错误 (参照 grok-build gap_fingerprint)"""
        normalized = sorted(set(g.strip().lower() for g in gaps))
        return hashlib.sha256(
            "|".join(normalized).encode()
        ).hexdigest()[:16]

    def record_classifier_result(self, verdict: str, gaps: list[str] = None):
        """记录验证结果并检测停滞"""
        self.classifier_runs_attempted += 1
        self.last_classifier_verdict = verdict
        self.rounds_since_verify = 0

        if verdict == "Achieved":
            self.consecutive_not_achieved = 0
            self.classifier_stall_count = 0
            self.last_gap_fingerprint = None
            self.last_strategist_fired_at = 0
            return {"stalled": False, "need_strategist": False}

        # NotAchieved
        self.consecutive_not_achieved += 1

        if gaps:
            fp = self.fingerprint_gaps(gaps)
            if fp == self.last_gap_fingerprint:
                self.classifier_stall_count += 1
            else:
                self.classifier_stall_count = 1
                self.last_gap_fingerprint = fp

        # 停滞检测 — 连续3次相同缺口
        stalled = self.classifier_stall_count >= 3
        # 策略师触发 — 每隔 N 次连续失败
        strategist_every = 3
        need_strategist = (
            self.consecutive_not_achieved >=
            self.last_strategist_fired_at + strategist_every
        )

        if need_strategist:
            self.last_strategist_fired_at = self.consecutive_not_achieved

        return {"stalled": stalled, "need_strategist": need_strategist}

    def capture_plan_baseline(self, plan_text: str):
        """捕获基准计划快照 (参照 grok-build plan_baseline_file)"""
        self.plan_baseline = plan_text

    def diff_against_baseline(self, current_plan: str) -> dict:
        """对比当前计划 vs 基准计划"""
        if not self.plan_baseline:
            return {"changed": False, "reason": "无基准计划"}
        import difflib
        diff = list(difflib.unified_diff(
            self.plan_baseline.splitlines(),
            current_plan.splitlines(),
            lineterm="", n=0
        ))
        added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        return {
            "changed": added > 0 or removed > 0,
            "added_lines": added, "removed_lines": removed,
            "diff_preview": "\n".join(diff[:20]),
        }

    def live_stats(self) -> dict:
        """实时统计"""
        return {
            "context_window": self.live_context_window,
            "context_pct": self.live_context_pct,
            "turns": self.live_turn_count,
            "tool_calls": self.live_tool_call_count,
            "subagent_tokens": self.live_subagent_tokens,
            "token_budget": self.token_budget,
            "tokens_spent": self.parent_tokens_spent,
            "budget_remaining": (
                (self.token_budget - self.parent_tokens_spent)
                if self.token_budget else None
            ),
        }


@dataclass
class GoalTrackerV2:
    """Goal Tracker v2 — 完整 grok-build 模式"""

    agent: object
    orchestration: GoalOrchestration | None = None

    def is_active(self) -> bool:
        return (self.orchestration is not None and
                self.orchestration.status == GoalStatus.ACTIVE)

    def start_goal(self, objective: str, token_budget: int = None) -> str:
        """开始新目标 (参照 grok-build)"""
        self.orchestration = GoalOrchestration(
            objective=objective[:200],
            token_budget=token_budget,
            status=GoalStatus.ACTIVE,
            phase=GoalPhase.PLANNING,
        )
        # 创建任务卡片
        from memory.tasks import create_task
        create_task(objective[:80], objective, priority=5)

        # Token 基准
        from memory.db import get_db
        total_tokens = get_db().execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]
        self.orchestration.token_baseline = total_tokens
        self.orchestration.last_session_tokens_seen = total_tokens

        return self._plan(objective)

    def _plan(self, objective: str) -> str:
        """制定计划 — 参照 grok-build 的 planner subagent"""
        self.orchestration.planning_in_flight = True
        self.orchestration.phase = GoalPhase.PLANNING

        prompt = f"""你需要为以下目标制定执行计划。只列出简短的执行步骤，每步一行。

目标: {objective}

格式:
1. 第一步
2. 第二步
...（最多8步）"""

        from coordinator.engine import think
        plan_text = think(prompt)

        # 提取步骤
        steps = []
        for line in plan_text.split("\n"):
            line = line.strip()
            m = re.match(r'^\d+[\.\)]\s*(.+)', line)
            if m:
                step = m.group(1).strip()
                if 3 < len(step) < 80 and step not in steps:
                    steps.append(step)
        self.orchestration.capture_plan_baseline("\n".join(steps))

        self.orchestration.planning_in_flight = False
        self.orchestration.phase = GoalPhase.EXECUTING

        plan_lines = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps[:8]))
        return f"目标「{objective[:50]}」— {len(steps[:8])} 步计划:\n\n{plan_lines}\n\n开始执行..."

    def continue_goal(self, user_input: str) -> str:
        """继续执行 (参照 grok-build 的 continuation loop)"""
        if not self.orchestration:
            return self.agent.handle(user_input)

        self.orchestration.live_turn_count += 1

        # 更新 token 核算
        from memory.db import get_db
        total = get_db().execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]
        self.orchestration.record_token_spend(total * 500)  # 估算: 500 tokens/msg

        # 检查 token 预算
        if self.orchestration.token_budget:
            remaining = (self.orchestration.token_budget -
                         self.orchestration.parent_tokens_spent)
            if remaining <= 0 and not self.orchestration.budget_limit_reported:
                self.orchestration.status = GoalStatus.PAUSED
                return "⚠️ Token 预算用尽。目标已暂停。请确认是否继续。"

        # 执行下一步
        if self.orchestration.phase == GoalPhase.EXECUTING:
            return self._execute_next()

        if self.orchestration.phase == GoalPhase.VERIFYING:
            return self._verify(user_input)

        return self.agent.handle(user_input)

    def _execute_next(self) -> str:
        """执行下一步 + 缺口检测"""
        # 简化版: 直接让大脑执行
        result = self.agent.handle(self.orchestration.objective)
        self.orchestration.live_tool_call_count += 1
        self.orchestration.total_worker_rounds += 1

        # 进入验证
        if self.orchestration.total_worker_rounds >= 5:
            self.orchestration.phase = GoalPhase.VERIFYING
            return self._start_verification()

        return result

    def _start_verification(self) -> str:
        """开始验证 (参照 grok-build 的 classifier)"""
        self.orchestration.verifying_in_flight = True
        self.orchestration.phase = GoalPhase.VERIFYING
        self.orchestration.total_verify_rounds += 1

        # 简化版验证: 让大脑自己判断
        prompt = f"""你正在执行目标: {self.orchestration.objective}
已执行 {self.orchestration.total_worker_rounds} 轮。

请判断: 目标是否已达成？
回复 "Achieved" 或 "NotAchieved"，并说明原因。"""

        from coordinator.engine import think
        verdict_text = think(prompt)

        if "achieved" in verdict_text.lower():
            result = self.orchestration.record_classifier_result(
                "Achieved")
            self.orchestration.status = GoalStatus.ACHIEVED
            self.orchestration.verifying_in_flight = False
            return f"✅ 目标达成！共 {self.orchestration.total_worker_rounds} 轮。"

        # NotAchieved — 检测停滞
        gaps = [verdict_text[:100]]
        analysis = self.orchestration.record_classifier_result(
            "NotAchieved", gaps)

        self.orchestration.verifying_in_flight = False

        if analysis["stalled"]:
            self.orchestration.status = GoalStatus.PAUSED
            return ("⚠️ 检测到停滞 — 连续3次相同缺口。目标已暂停。\n"
                    "可能需要重新规划或人工介入。")

        if analysis["need_strategist"]:
            self.orchestration.phase = GoalPhase.PLANNING
            return ("🔄 策略师介入 — 需要重新规划。\n"
                    f"连续 {self.orchestration.consecutive_not_achieved} 次未达成。")

        self.orchestration.phase = GoalPhase.EXECUTING
        return f"继续执行... (第 {self.orchestration.total_verify_rounds} 轮验证未通过)"

    def _verify(self, user_input: str) -> str:
        """用户验证反馈"""
        if any(w in user_input for w in ["完成", "可以", "好", "ok", "done",
                                           "通过", "达成"]):
            self.orchestration.status = GoalStatus.ACHIEVED
            self.orchestration.record_classifier_result("Achieved")
            from memory.tasks import list_tasks, update_task
            tasks = list_tasks(status="active")
            if tasks: update_task(tasks[0]["id"], status="done")
            return f"✅ 目标「{self.orchestration.objective[:50]}」正式达成！"
        else:
            self.orchestration.phase = GoalPhase.EXECUTING
            return "收到反馈，继续调整。"

    def stats(self) -> dict:
        if not self.orchestration:
            return {"status": "idle"}
        return {
            "goal_id": self.orchestration.goal_id,
            "status": self.orchestration.status.value,
            "phase": self.orchestration.phase.value,
            "rounds": self.orchestration.total_worker_rounds,
            "verifications": self.orchestration.total_verify_rounds,
            "stall_count": self.orchestration.classifier_stall_count,
            "tokens_spent": self.orchestration.parent_tokens_spent,
            "live": self.orchestration.live_stats(),
        }
