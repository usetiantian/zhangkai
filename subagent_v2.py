"""Subagent Coordinator v2 — 完整生命周期 (移植自 grok-build coordinator_lifecycle)"""

import time, uuid, threading
from dataclasses import dataclass, field
from enum import Enum


class SubagentState(Enum):
    PENDING = "pending"
    ACTIVE = "active"  
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentTracker:
    """子 Agent 追踪器 (移植自 grok-build)"""
    id: str
    description: str = ""
    tool: str = ""
    params: dict = field(default_factory=dict)
    state: SubagentState = SubagentState.PENDING
    result: str = ""
    error: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    prompt_index: int = 0

    def __post_init__(self):
        self.created_at = time.time()


@dataclass
class SubagentCompletionSummary:
    """完成摘要"""
    id: str
    state: SubagentState
    description: str
    result_preview: str


class SubagentCoordinatorV2:
    """
    子 Agent 协调器 v2 — 完整生命周期管理.
    
    移植自 grok-build SubagentCoordinator:
    - pending → active → completed 状态机
    - completion_notify 完成通知
    - running_gauge 运行计数
    - block_wait_slots 等待槽
    """

    def __init__(self):
        self.pending: dict[str, SubagentTracker] = {}
        self.active: dict[str, SubagentTracker] = {}
        self.completed: dict[str, SubagentTracker] = {}
        self.failed: dict[str, SubagentTracker] = {}
        
        self._completion_notify = threading.Event()
        self._completion_lock = threading.Lock()
        self.pending_completions: list[SubagentCompletionSummary] = []
        self._running_gauge: int = 0

    def spawn(self, description: str, tool: str = "",
              params: dict = None) -> str:
        """派生子 Agent"""
        tracker = SubagentTracker(
            id=str(uuid.uuid4())[:8],
            description=description,
            tool=tool,
            params=params or {},
        )
        self.pending[tracker.id] = tracker
        return tracker.id

    def spawn_parallel(self, tasks: list[dict]) -> list[str]:
        """并行派发"""
        return [self.spawn(t.get("description", ""),
                          t.get("tool", ""),
                          t.get("params", {}))
                for t in tasks]

    def run_pending(self, executor_func) -> list[SubagentCompletionSummary]:
        """执行所有 pending 任务"""
        task_ids = list(self.pending.keys())
        if not task_ids:
            return []

        threads = []
        for tid in task_ids:
            tracker = self.pending[tid]
            tracker.state = SubagentState.ACTIVE
            tracker.started_at = time.time()
            self.active[tid] = tracker
            self._running_gauge += 1

            t = threading.Thread(
                target=self._run_one,
                args=(tracker, executor_func),
                daemon=True,
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 收集结果
        completions = []
        for tid in task_ids:
            if tid in self.completed:
                t = self.completed[tid]
            elif tid in self.failed:
                t = self.failed[tid]
            else:
                continue
            
            completions.append(SubagentCompletionSummary(
                id=t.id,
                state=t.state,
                description=t.description,
                result_preview=(t.result or t.error)[:200],
            ))

        self.pending_completions.extend(completions)
        self._completion_notify.set()
        return completions

    def _run_one(self, tracker: SubagentTracker, executor_func):
        """执行单个子 Agent"""
        try:
            result = executor_func(tracker)
            tracker.result = str(result)[:5000]
            tracker.state = SubagentState.COMPLETED
            tracker.completed_at = time.time()
            
            with self._completion_lock:
                if tracker.id in self.active:
                    del self.active[tracker.id]
                self.completed[tracker.id] = tracker
        except Exception as e:
            tracker.error = str(e)
            tracker.state = SubagentState.FAILED
            tracker.completed_at = time.time()
            
            with self._completion_lock:
                if tracker.id in self.active:
                    del self.active[tracker.id]
                self.failed[tracker.id] = tracker
        finally:
            self._running_gauge -= 1

    def cancel(self, subagent_id: str) -> bool:
        """取消子 Agent"""
        if subagent_id in self.pending:
            self.pending[subagent_id].state = SubagentState.CANCELLED
            del self.pending[subagent_id]
            return True
        return False

    def is_busy(self) -> bool:
        return len(self.pending) > 0 or len(self.active) > 0

    def running_count(self) -> int:
        return self._running_gauge

    def drain_completions(self) -> list[SubagentCompletionSummary]:
        """取出完成的子 Agent 摘要"""
        result = list(self.pending_completions)
        self.pending_completions.clear()
        return result

    def stats(self) -> dict:
        return {
            "pending": len(self.pending),
            "active": len(self.active),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "running_gauge": self._running_gauge,
        }
