"""Circuit Breaker — 熔断器 (移植自 grok-build circuit-breaker)"""

import time, threading
from enum import Enum
from dataclasses import dataclass, field


class BreakerState(Enum):
    CLOSED = "closed"       # 正常
    OPEN = "open"           # 熔断
    HALF_OPEN = "half_open" # 半开 (试探)


@dataclass
class CircuitBreaker:
    """
    熔断器 — Closed → Open → HalfOpen → Closed 状态机.
    
    移植自 grok-build xai-circuit-breaker.
    """
    name: str = "default"
    min_samples: int = 3           # 最小样本数才判断
    error_rate_threshold: float = 0.5  # 错误率阈值
    open_duration: float = 30.0    # 熔断持续时间 (秒)
    max_half_open_probes: int = 1  # 半开时最大试探数

    _state: str = field(default="closed", init=False)
    _successes: int = field(default=0, init=False)
    _failures: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)
    _half_open_probes: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return BreakerState(self._state)

    def check(self) -> tuple[bool, str]:
        """
        检查是否可以执行。
        返回 (是否可以, 原因)。
        """
        with self._lock:
            if self._state == "closed":
                return True, "ok"

            if self._state == "open":
                elapsed = time.time() - self._opened_at
                if elapsed >= self.open_duration:
                    self._state = "half_open"
                    self._half_open_probes = 0
                    return True, "half_open_probe"
                return False, f"熔断中 ({elapsed:.0f}s / {self.open_duration}s)"

            if self._state == "half_open":
                if self._half_open_probes < self.max_half_open_probes:
                    self._half_open_probes += 1
                    return True, "half_open_probe"
                return False, "半开试探已达上限"

            return False, "unknown"

    def record(self, outcome: str):
        """记录一次结果 (success / failure)"""
        with self._lock:
            if outcome == "success":
                self._successes += 1
            else:
                self._failures += 1

            total = self._successes + self._failures
            if total < self.min_samples:
                return

            error_rate = self._failures / total

            if self._state == "closed" and error_rate >= self.error_rate_threshold:
                self._state = "open"
                self._opened_at = time.time()

            elif self._state == "half_open":
                if outcome == "success":
                    self._state = "closed"
                    self._successes = 0
                    self._failures = 0
                else:
                    self._state = "open"
                    self._opened_at = time.time()

    def reset(self):
        """手动重置"""
        with self._lock:
            self._state = "closed"
            self._successes = 0
            self._failures = 0
            self._half_open_probes = 0

    def stats(self) -> dict:
        with self._lock:
            total = self._successes + self._failures
            return {
                "name": self.name,
                "state": self._state,
                "successes": self._successes,
                "failures": self._failures,
                "total": total,
                "error_rate": round(self._failures / total, 3) if total > 0 else 0,
            }
