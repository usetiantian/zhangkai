# -*- coding: utf-8 -*-
"""DAG Workflow Engine — Airflow/Prefect-style parallel task orchestration."""
import asyncio, logging, time, uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set

logger = logging.getLogger(__name__)

class StepStatus(Enum):
    PENDING="pending"; RUNNING="running"; DONE="done"; FAILED="failed"; SKIPPED="skipped"

@dataclass
class WorkflowStep:
    id: str; name: str; fn: Optional[Callable]=None
    depends_on: List[str]=field(default_factory=list)
    status: StepStatus=StepStatus.PENDING
    result: Any=None; error: str=""; started_at: float=0; completed_at: float=0
    retries: int=0; max_retries: int=2; timeout: float=120.0
    metadata: Dict=field(default_factory=dict)

@dataclass
class Workflow:
    id: str; name: str; steps: Dict[str, WorkflowStep]=field(default_factory=dict)
    status: StepStatus=StepStatus.PENDING
    created_at: float=field(default_factory=time.time)
    completed_at: float=0
    parallel_limit: int=5  # Max concurrent steps

class WorkflowEngine:
    """DAG-based parallel workflow executor."""

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._active: Set[str] = set()
        self._semaphore: Optional[asyncio.Semaphore] = None

    def create(self, name: str, steps: List[Dict]) -> Workflow:
        """Create a workflow from step definitions.
        Each step: {name, depends_on:[], fn:Callable, timeout:float, max_retries:int}
        """
        wf = Workflow(id=uuid.uuid4().hex[:8], name=name)
        for s in steps:
            step = WorkflowStep(
                id=uuid.uuid4().hex[:6], name=s["name"],
                fn=s.get("fn"), depends_on=s.get("depends_on", []),
                timeout=s.get("timeout", 120.0), max_retries=s.get("max_retries", 2),
                metadata=s.get("metadata", {}),
            )
            wf.steps[step.name] = step
        self._workflows[wf.id] = wf
        # Validate DAG
        if not self._is_dag(wf):
            raise ValueError(f"Workflow '{name}' contains cycles")
        logger.info("[Workflow] Created: %s (%d steps)", name, len(wf.steps))
        return wf

    def _is_dag(self, wf: Workflow) -> bool:
        """Check for cycles using topological sort."""
        in_degree = {name: len(step.depends_on) for name, step in wf.steps.items()}
        adj = defaultdict(list)
        for name, step in wf.steps.items():
            for dep in step.depends_on:
                if dep in wf.steps:
                    adj[dep].append(name)

        queue = [n for n, d in in_degree.items() if d == 0]
        visited = 0

        while queue:
            node = queue.pop(0)
            visited += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited == len(wf.steps)

    async def run(self, workflow_id: str, context: dict = None) -> Dict:
        """Execute a workflow with parallel step execution."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"status": "not_found"}
        if workflow_id in self._active:
            return {"status": "already_running"}

        self._active.add(workflow_id)
        wf.status = StepStatus.RUNNING
        self._semaphore = asyncio.Semaphore(wf.parallel_limit)

        # Build dependency graph
        pending: Dict[str, Set[str]] = {}
        for name, step in wf.steps.items():
            pending[name] = set(step.depends_on)

        completed: Set[str] = set()
        failed: Set[str] = set()
        running: Set[str] = set()

        async def _execute_step(name: str):
            step = wf.steps[name]
            step.status = StepStatus.RUNNING
            step.started_at = time.time()

            try:
                async with self._semaphore:
                    if step.fn:
                        result = await asyncio.wait_for(
                            step.fn(context) if asyncio.iscoroutinefunction(step.fn)
                            else asyncio.get_event_loop().run_in_executor(None, step.fn, context),
                            timeout=step.timeout,
                        )
                        step.result = result
                step.status = StepStatus.DONE
                completed.add(name)
            except asyncio.TimeoutError:
                step.error = f"timeout after {step.timeout}s"
                if step.retries < step.max_retries:
                    step.retries += 1
                    logger.info("[Workflow] Retry %s (%d/%d)", name, step.retries, step.max_retries)
                    step.status = StepStatus.PENDING
                else:
                    step.status = StepStatus.FAILED
                    failed.add(name)
            except Exception as e:
                step.error = str(e)[:200]
                if step.retries < step.max_retries:
                    step.retries += 1
                    step.status = StepStatus.PENDING
                else:
                    step.status = StepStatus.FAILED
                    failed.add(name)
            finally:
                step.completed_at = time.time()
                if name in running:
                    running.discard(name)

        # Main execution loop
        while len(completed) + len(failed) < len(wf.steps):
            # Find ready steps (all deps completed)
            ready = []
            for name in wf.steps:
                if name in completed or name in failed or name in running:
                    continue
                if pending[name].issubset(completed):
                    ready.append(name)

            if not ready and not running:
                # Deadlock — remaining steps can't be satisfied
                stuck = [n for n in wf.steps if n not in completed and n not in failed]
                for n in stuck:
                    wf.steps[n].status = StepStatus.FAILED
                    wf.steps[n].error = "deadlock: unsatisfied dependencies"
                    failed.add(n)
                break

            # Execute ready steps in parallel
            tasks = []
            for name in ready:
                running.add(name)
                tasks.append(asyncio.create_task(_execute_step(name)))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        wf.status = StepStatus.DONE if not failed else StepStatus.FAILED
        wf.completed_at = time.time()
        self._active.discard(workflow_id)

        done_count = len(completed)
        fail_count = len(failed)
        logger.info("[Workflow] %s: %d done, %d failed (%.0fs)",
                    wf.name, done_count, fail_count, wf.completed_at - wf.created_at)

        return {
            "status": wf.status.value, "done": done_count, "failed": fail_count,
            "total": len(wf.steps), "duration_s": round(wf.completed_at - wf.created_at, 1),
            "failed_steps": list(failed),
        }

    def get_status(self, workflow_id: str) -> Optional[Dict]:
        wf = self._workflows.get(workflow_id)
        if not wf: return None
        return {
            "name": wf.name, "status": wf.status.value,
            "steps": {n: s.status.value for n, s in wf.steps.items()},
            "progress": f"{sum(1 for s in wf.steps.values() if s.status==StepStatus.DONE)}/{len(wf.steps)}",
        }

    def get_stats(self) -> Dict:
        return {
            "total_workflows": len(self._workflows),
            "active": len(self._active),
            "completed": sum(1 for w in self._workflows.values() if w.status==StepStatus.DONE),
            "failed": sum(1 for w in self._workflows.values() if w.status==StepStatus.FAILED),
        }


_engine: Optional[WorkflowEngine] = None
def get_workflow_engine() -> WorkflowEngine:
    global _engine
    if _engine is None: _engine = WorkflowEngine()
    return _engine
