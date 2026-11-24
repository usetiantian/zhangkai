"""Agent Lifecycle — 生命周期 + 扩展注册 (移植自 grok-build xai-agent-lifecycle)"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class LifecycleEvent(Enum):
    """grok-build lifecycle events"""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_LOAD = "session_load"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"
    MODEL_SWITCH = "model_switch"
    COMPACTION = "compaction"
    GOAL_START = "goal_start"
    GOAL_END = "goal_end"
    SUBAGENT_SPAWN = "subagent_spawn"
    SUBAGENT_COMPLETE = "subagent_complete"
    INTERJECTION = "interjection"
    ERROR = "error"


@dataclass
class LifecycleContext:
    """生命周期上下文"""
    event: LifecycleEvent
    session_id: str = ""
    data: dict = field(default_factory=dict)


# 扩展贡献者类型
SessionLifecycleContributor = Callable[[LifecycleContext], None]
TurnLifecycleContributor = Callable[[LifecycleContext], None]


class ExtensionRegistry:
    """
    扩展注册表.
    
    移植自 grok-build xai-agent-lifecycle ExtensionRegistry.
    管理 session 和 turn 两个级别的生命周期回调。
    """
    def __init__(self):
        self._session_contributors: list[SessionLifecycleContributor] = []
        self._turn_contributors: list[TurnLifecycleContributor] = []

    def register_session(self, contributor: SessionLifecycleContributor):
        """注册 session 级别回调"""
        self._session_contributors.append(contributor)

    def register_turn(self, contributor: TurnLifecycleContributor):
        """注册 turn 级别回调"""
        self._turn_contributors.append(contributor)

    def emit(self, event: LifecycleEvent, session_id: str = "", **data):
        """触发生命周期事件"""
        ctx = LifecycleContext(event=event, session_id=session_id, data=data)

        # Session 级事件
        if event in (LifecycleEvent.SESSION_START, LifecycleEvent.SESSION_END,
                     LifecycleEvent.SESSION_LOAD, LifecycleEvent.GOAL_START,
                     LifecycleEvent.GOAL_END, LifecycleEvent.ERROR):
            for c in self._session_contributors:
                try:
                    c(ctx)
                except Exception:
                    pass

        # Turn 级事件
        if event in (LifecycleEvent.TURN_START, LifecycleEvent.TURN_END,
                     LifecycleEvent.TOOL_CALL_START, LifecycleEvent.TOOL_CALL_END,
                     LifecycleEvent.TOOL_RESULT, LifecycleEvent.MODEL_SWITCH,
                     LifecycleEvent.COMPACTION, LifecycleEvent.SUBAGENT_SPAWN,
                     LifecycleEvent.SUBAGENT_COMPLETE, LifecycleEvent.INTERJECTION):
            for c in self._turn_contributors:
                try:
                    c(ctx)
                except Exception:
                    pass


# 内置扩展
def _log_to_memory(ctx: LifecycleContext):
    """内置: 记录到记忆"""
    try:
        from memory.db import get_db
        get_db().execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, 'system', ?)",
            (ctx.session_id, f"[{ctx.event.value}]")
        )
        get_db().commit()
    except Exception:
        pass


def _update_self_model(ctx: LifecycleContext):
    """内置: 更新自我认知"""
    if ctx.event == LifecycleEvent.TOOL_RESULT:
        try:
            from knowledge.self_model import update
            tool = ctx.data.get("tool_name", "general")
            ok = ctx.data.get("success", True)
            domain_map = {"search": "search", "fetch": "fetch",
                         "run_code": "code_gen", "create_task": "task_planning"}
            update(domain_map.get(tool, "general"), 0.8 if ok else 0.3)
        except Exception:
            pass


def create_default_registry() -> ExtensionRegistry:
    """创建带内置扩展的注册表"""
    reg = ExtensionRegistry()
    reg.register_session(_log_to_memory)
    reg.register_turn(_log_to_memory)
    reg.register_turn(_update_self_model)
    return reg
