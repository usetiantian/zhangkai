"""七层自愈——借鉴ClaudeCode七层恢复策略"""
import time, logging
logger = logging.getLogger("nexus.recovery")

class RecoveryEngine:
    def __init__(self):
        self._fails = {}
        self._breakers = {}

    def retry(self, fn, key: str, max_tries=5, base_delay=1.0):
        for i in range(max_tries):
            try: return fn()
            except Exception as e:
                delay = min(base_delay * (2**i), 60)
                if i < max_tries-1: time.sleep(delay)
        raise RuntimeError(f"[{key}] all {max_tries} retries failed")

    def model_fallback(self, current="4B"):
        chain = {"4B": "2B", "2B": "rules"}
        return chain.get(current, "rules")

    def persistent_retry(self, task: str, max_tries=3) -> bool:
        self._fails[task] = self._fails.get(task, 0) + 1
        return self._fails[task] <= max_tries

    def circuit_breaker(self, key: str, max_fails=5) -> bool:
        if self._breakers.get(key): return False
        self._fails[key] = self._fails.get(key, 0) + 1
        if self._fails[key] >= max_fails:
            self._breakers[key] = True
            return False
        return True
