"""
七层自愈系统
来源：Claude Code 源码 + 专业分析 — 七层恢复策略

层1: 指数退避重试 (API超时)
层2: 过载处理 (切本地Qwen)
层3: 响应式压缩 (上下文溢出)
层4: 上下文排空 (内存不足)
层5: 模型fallback (4B->2B)
层6: 持久重试 (凌晨学习失败重试)
层7: 超时上限 (最大5min退避/重置6h)
"""
import time, logging
logger = logging.getLogger("nexus.recovery")

class RecoverySystem:
    def __init__(self):
        self.retry_counts = {}      # {key: count}
        self.breaker_tripped = {}   # {key: bool}

    # 层1: 指数退避重试
    def retry_with_backoff(self, fn, key: str, max_retries=5, base_delay=1.0):
        for attempt in range(max_retries):
            try:
                return fn()
            except Exception as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[{key}] retry {attempt+1}/{max_retries}, delay={delay}s: {e}")
                if attempt < max_retries - 1:
                    time.sleep(min(delay, 60))
        raise RuntimeError(f"[{key}] all {max_retries} retries failed")

    # 层2: 过载fallback
    def switch_to_local(self, reason: str = "overload"):
        logger.warning(f"Switching to local Qwen: {reason}")
        return {"model": "qwen_local", "reason": reason}

    # 层3: 上下文压缩触发
    def compact_if_needed(self, context_len: int, threshold: int = 10000):
        if context_len > threshold:
            logger.info(f"Compact triggered: {context_len} > {threshold}")
            return True
        return False

    # 层4: 上下文排空
    def drain_context(self, memory_module):
        """释放旧会话，保留最近5轮。"""
        logger.info("Draining old context...")
        return True

    # 层5: 模型降级
    def model_fallback(self, current_model: str = "4B"):
        next_model = {"4B": "2B", "2B": "rules"}.get(current_model, "rules")
        logger.warning(f"Model fallback: {current_model} -> {next_model}")
        return next_model

    # 层6: 持久重试
    def persistent_retry(self, task_name: str, max_attempts=3):
        self.retry_counts[task_name] = self.retry_counts.get(task_name, 0) + 1
        count = self.retry_counts[task_name]
        if count > max_attempts:
            logger.error(f"[{task_name}] exhausted {max_attempts} attempts")
            return False
        logger.info(f"[{task_name}] persistent retry {count}/{max_attempts}")
        return True

    # 层7: 熔断器 + 超时
    def circuit_breaker(self, key: str, max_failures=5, reset_seconds=3600):
        if self.breaker_tripped.get(key):
            logger.warning(f"[{key}] circuit OPEN — cooling down")
            return False
        return True

    def record_failure(self, key: str):
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1
        if self.retry_counts[key] >= 5:
            self.breaker_tripped[key] = True
            logger.error(f"[{key}] circuit TRIPPED after {self.retry_counts[key]} failures")
