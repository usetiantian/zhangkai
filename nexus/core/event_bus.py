"""
Nexus EventBus — 模块间唯一通信通道

铁律：
- 模块间不直接 import
- 所有通信走 EventBus
- 一个模块挂了不影响其他
"""
import logging
from collections import defaultdict
from typing import Callable, Any

logger = logging.getLogger("nexus.bus")

class EventBus:
    """全局事件总线。单例。"""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._health: dict[str, bool] = {}  # 模块健康状态

    def subscribe(self, event: str, handler: Callable, module: str = "unknown"):
        """订阅事件。event 用点号分隔: 'memory.updated'"""
        self._subscribers[event].append(handler)
        self._health[module] = True
        logger.debug(f"[{module}] subscribed to '{event}'")

    def publish(self, event: str, data: Any = None, *, source: str = "unknown"):
        """发布事件。一个订阅者挂了不影响其他。"""
        handlers = self._subscribers.get(event, [])
        for h in handlers:
            try:
                h(data)
            except Exception as e:
                logger.warning(f"[{source}] handler for '{event}' failed: {e}")
                # 不抛出，不阻塞其他 handler

    def module_dead(self, module: str):
        """标记模块死亡，其他模块可据此降级。"""
        self._health[module] = False
        logger.error(f"[{module}] DEAD — 其他模块将收到降级通知")
        self.publish("module.dead", {"module": module}, source=module)

    def module_alive(self, module: str):
        self._health[module] = True
        self.publish("module.alive", {"module": module}, source=module)

    def is_alive(self, module: str) -> bool:
        return self._health.get(module, False)


# 全局单例
bus = EventBus()
