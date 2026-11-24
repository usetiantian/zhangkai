"""Tool Runtime — 执行生命周期 (移植自 grok-build xai-tool-runtime)"""

import time, threading
from enum import Enum
from dataclasses import dataclass, field


class ExecutionState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FAILED = "failed"
    BACKGROUNDED = "backgrounded"


@dataclass
class ExecutionNotification:
    """执行通知 (对应 BashExecutionComplete/Timeout/Failed)"""
    tool_name: str
    state: ExecutionState
    exit_code: int | None = None
    signal: str | None = None  # SIGKILL etc
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    error: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        self.timestamp = time.time()


class ToolRuntime:
    """
    工具执行运行时.
    
    移植自 grok-build xai-tool-runtime:
    - 状态机: PENDING → RUNNING → COMPLETED / TIMEOUT / FAILED
    - 后台执行支持
    - 完成/超时/失败通知
    """
    def __init__(self, timeout_sec: float = 30.0):
        self.timeout_sec = timeout_sec
        self._listeners: list = []
        self._active: dict[str, ExecutionNotification] = {}

    def on_complete(self, callback):
        """注册完成回调"""
        self._listeners.append(callback)

    def execute(self, tool_name: str, func, **kwargs) -> ExecutionNotification:
        """同步执行工具"""
        start = time.time()

        notif = ExecutionNotification(
            tool_name=tool_name,
            state=ExecutionState.RUNNING,
        )

        try:
            result = func(**kwargs) if kwargs else func()
            duration = (time.time() - start) * 1000

            notif.state = ExecutionState.COMPLETED
            notif.exit_code = 0
            notif.stdout = str(result)[:5000]
            notif.duration_ms = int(duration)

        except Exception as e:
            duration = (time.time() - start) * 1000
            notif.state = ExecutionState.FAILED
            notif.error = str(e)
            notif.duration_ms = int(duration)

            if duration / 1000 >= self.timeout_sec:
                notif.state = ExecutionState.TIMEOUT

        self._notify(notif)
        return notif

    def execute_background(self, tool_name: str, func, **kwargs) -> str:
        """后台执行 — 返回 execution_id"""
        import uuid
        exec_id = str(uuid.uuid4())[:8]
        
        def _run():
            notif = self.execute(tool_name, func, **kwargs)
            self._active[exec_id] = notif

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        notif = ExecutionNotification(
            tool_name=tool_name,
            state=ExecutionState.BACKGROUNDED,
        )
        self._active[exec_id] = notif
        return exec_id

    def check_background(self, exec_id: str) -> ExecutionNotification | None:
        """检查后台任务状态"""
        return self._active.get(exec_id)

    def _notify(self, notif: ExecutionNotification):
        for cb in self._listeners:
            try:
                cb(notif)
            except Exception:
                pass
