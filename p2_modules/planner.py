# -*- coding: utf-8 -*-
"""
Hierarchical Task Network Planner — SHOP2/GoAP-style goal decomposition.
Industry standard: HTN planning + milestone tracking + dynamic replanning.
"""
import asyncio, logging, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING="pending"; RUNNING="running"; DONE="done"; FAILED="failed"; BLOCKED="blocked"; CANCELLED="cancelled"

class TaskPriority(Enum):
    CRITICAL=0; HIGH=1; MEDIUM=2; LOW=3; BACKGROUND=4

@dataclass
class Milestone:
    id: str; description: str; verify_fn: Optional[str]=None; done: bool=False

@dataclass
class PlannedTask:
    id: str; description: str; parent_id: Optional[str]=None
    children: List["PlannedTask"]=field(default_factory=list)
    status: TaskStatus=TaskStatus.PENDING
    priority: TaskPriority=TaskPriority.MEDIUM
    milestones: List[Milestone]=field(default_factory=list)
    agent: str="default"; deadline: float=0; retries: int=0; max_retries: int=3
    result: Any=None; error: str=""; started_at: float=0; completed_at: float=0

@dataclass
class Plan:
    id: str; goal: str; root: PlannedTask; status: TaskStatus=TaskStatus.PENDING
    created_at: float=field(default_factory=time.time)
    metrics: Dict=field(default_factory=lambda: {"tasks_total":0,"tasks_done":0,"tasks_failed":0,"depth":0})

class HTNPlanner:
    """Hierarchical Task Network planner with dynamic decomposition."""

    DECOMPOSITION_RULES = {
        "implement_feature": [
            ("understand_requirements",["analyze_spec","check_existing_code"]),
            ("design_solution",["choose_approach","validate_design"]),
            ("implement",["write_code","add_tests","integrate"]),
            ("verify",["run_tests","review_code","deploy"]),
        ],
        "fix_bug": [
            ("reproduce",["isolate","create_minimal_case"]),
            ("diagnose",["trace_execution","identify_root_cause"]),
            ("fix",["apply_patch","verify_fix"]),
            ("prevent",["add_regression_test","document_lessons"]),
        ],
        "learn_topic": [
            ("research",["search_sources","evaluate_credibility"]),
            ("synthesize",["extract_key_points","cross_reference"]),
            ("internalize",["store_knowledge","connect_to_existing"]),
        ],
        "optimize_system": [
            ("profile",["measure_baseline","identify_bottlenecks"]),
            ("plan_optimization",["prioritize_improvements","estimate_impact"]),
            ("implement",["apply_optimization","benchmark"]),
            ("validate",["regression_test","monitor_production"]),
        ],
    }

    def __init__(self):
        self._plans: Dict[str, Plan] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._stats = {"plans_created": 0, "plans_completed": 0, "plans_failed": 0}

    def register_handler(self, task_type: str, handler: Callable):
        self._task_handlers[task_type] = handler

    def plan(self, goal: str, context: dict = None, max_depth: int = 3) -> Plan:
        """Decompose a goal into executable sub-tasks using HTN rules."""
        plan_id = uuid.uuid4().hex[:12]
        root = PlannedTask(id=f"{plan_id}_root", description=goal)
        self._decompose(root, goal, max_depth)
        plan = Plan(id=plan_id, goal=goal, root=root)
        plan.metrics["tasks_total"] = self._count_tasks(root)
        plan.metrics["depth"] = self._max_depth(root)
        self._plans[plan_id] = plan
        self._stats["plans_created"] += 1
        logger.info("[Planner] Plan %s: %s → %d tasks (depth=%d)",
                    plan_id, goal[:60], plan.metrics["tasks_total"], plan.metrics["depth"])
        return plan

    def _decompose(self, parent: PlannedTask, goal: str, depth: int):
        if depth <= 0:
            return

        # Find matching decomposition rule
        best_match = None
        best_score = 0
        for rule_key, steps in self.DECOMPOSITION_RULES.items():
            score = self._match_score(goal, rule_key)
            if score > best_score:
                best_score = score
                best_match = steps

        if best_match and best_score > 0.3:
            for step_name, sub_steps in best_match:
                child = PlannedTask(
                    id=uuid.uuid4().hex[:8],
                    description=step_name,
                    parent_id=parent.id,
                    priority=self._infer_priority(step_name),
                )
                for sub in sub_steps[:3]:
                    sub_child = PlannedTask(
                        id=uuid.uuid4().hex[:8],
                        description=sub,
                        parent_id=child.id,
                    )
                    child.children.append(sub_child)
                parent.children.append(child)
        else:
            # Can't decompose further — leaf task
            pass

    def _match_score(self, goal: str, rule_key: str) -> float:
        goal_lower = goal.lower()
        rule_lower = rule_key.lower()
        if rule_lower in goal_lower or goal_lower in rule_lower:
            return 1.0
        rule_words = set(rule_lower.split("_"))
        goal_words = set(goal_lower.replace("_"," ").split())
        overlap = rule_words & goal_words
        return len(overlap) / max(len(rule_words), 1)

    def _infer_priority(self, step_name: str) -> TaskPriority:
        if any(kw in step_name for kw in ['fix','implement','deploy','security','bug']):
            return TaskPriority.HIGH
        elif any(kw in step_name for kw in ['test','verify','validate','diagnose']):
            return TaskPriority.MEDIUM
        return TaskPriority.LOW

    def _count_tasks(self, task: PlannedTask) -> int:
        return 1 + sum(self._count_tasks(c) for c in task.children)

    def _max_depth(self, task: PlannedTask, d: int = 1) -> int:
        if not task.children:
            return d
        return max(self._max_depth(c, d + 1) for c in task.children)

    async def execute(self, plan_id: str, executor: Callable = None) -> Dict:
        """Execute a plan by traversing the task tree."""
        plan = self._plans.get(plan_id)
        if not plan:
            return {"status": "not_found"}

        plan.status = TaskStatus.RUNNING
        try:
            await self._execute_task(plan.root, executor or self._default_executor)
            all_done = all(
                self._all_done(plan.root)
            )
            if all_done:
                plan.status = TaskStatus.DONE
                self._stats["plans_completed"] += 1
        except Exception as e:
            plan.status = TaskStatus.FAILED
            self._stats["plans_failed"] += 1
            logger.error("[Planner] Plan %s failed: %s", plan_id, e)

        plan.metrics["tasks_done"] = self._count_done(plan.root)
        return {"status": plan.status.value, "done": plan.metrics["tasks_done"],
                "total": plan.metrics["tasks_total"]}

    async def _execute_task(self, task: PlannedTask, executor: Callable):
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        try:
            if task.children:
                for child in task.children:
                    await self._execute_task(child, executor)
            else:
                task.result = await executor(task.description, task.id)
            task.status = TaskStatus.DONE
        except Exception as e:
            task.error = str(e)[:200]
            task.retries += 1
            if task.retries < task.max_retries:
                logger.info("[Planner] Retry %s (%d/%d)", task.id, task.retries, task.max_retries)
                await self._execute_task(task, executor)
            else:
                task.status = TaskStatus.FAILED
        task.completed_at = time.time()

    async def _default_executor(self, description: str, task_id: str) -> str:
        logger.info("[Planner] Execute: %s (%s)", description[:80], task_id)
        return f"executed: {description[:60]}"

    def _all_done(self, task: PlannedTask) -> bool:
        if task.status != TaskStatus.DONE:
            return False
        return all(self._all_done(c) for c in task.children)

    def _count_done(self, task: PlannedTask) -> int:
        return (1 if task.status == TaskStatus.DONE else 0) + sum(self._count_done(c) for c in task.children)

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self._plans.get(plan_id)

    def get_stats(self) -> Dict:
        return {**self._stats, "active_plans": len([p for p in self._plans.values() if p.status == TaskStatus.RUNNING])}


_planner: Optional[HTNPlanner] = None
def get_planner() -> HTNPlanner:
    global _planner
    if _planner is None: _planner = HTNPlanner()
    return _planner
