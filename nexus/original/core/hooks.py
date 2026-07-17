"""
Hook 生命周期系统
来源：Claude Code 24事件×6类型 + Grok Build hook discovery 融合

6种Hook类型: start/think/act/reflect/error/periodic
每个模块可注册任意类型，按优先级执行
"""
import time, logging
from collections import defaultdict
logger = logging.getLogger("nexus.hooks")

class HookSystem:
    """技能生命周期钩子系统。"""
    def __init__(self):
        self._hooks = defaultdict(list)  # {event: [(priority, handler, module)]}

    def register(self, event: str, handler, module: str = "unknown", priority: int = 5):
        """注册钩子。优先级1最高。"""
        self._hooks[event].append((priority, handler, module))
        self._hooks[event].sort()  # 按优先级排序
        logger.debug(f"[{module}] hooked '{event}' p={priority}")

    def trigger(self, event: str, data: dict = None) -> list:
        """触发钩子链。一个失败不影响后续。"""
        results = []
        for _, handler, module in self._hooks.get(event, []):
            try:
                result = handler(data or {})
                results.append({"module": module, "ok": True, "result": result})
            except Exception as e:
                logger.warning(f"Hook[{event}] {module} failed: {e}")
                results.append({"module": module, "ok": False, "error": str(e)})
        return results

# 预定义事件常量
EVENTS = {
    "session_start":  "会话启动—加载记忆/检查更新",
    "pre_input":      "用户输入前—权限预检",
    "post_input":     "用户输入后—写入短期记忆",
    "pre_think":      "推理前—注入Constitution",
    "post_think":     "推理后—记录决策",
    "pre_act":        "执行前—熔断器检查",
    "post_act":       "执行后—经验银行写入",
    "error":          "出错—错误分类+自动恢复",
    "periodic":       "定时—心跳检查+学习调度",
    "session_end":    "会话结束—checkpoint保存",
}
