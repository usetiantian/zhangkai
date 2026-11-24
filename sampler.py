"""Sampler — 推理调度 + 重试退避 + 错误分类 (移植自 grok-build sampler/retry)"""

import time, random, hashlib
from dataclasses import dataclass
from enum import Enum


class RetryDecision(Enum):
    RETRY = "retry"
    RETRY_WITH_NEW_CLIENT = "retry_with_new_client"
    DOOM_LOOP = "doom_loop"
    FATAL = "fatal"


class ErrorClass(Enum):
    TRANSIENT = "transient"       # 临时错误，可重试
    RATE_LIMIT = "rate_limit"     # 限流
    AUTH = "auth"                  # 认证错误，不可重试
    CONTEXT_OVERFLOW = "context_overflow"  # 上下文超限
    STREAM = "stream"             # 流错误
    FATAL = "fatal"              # 致命错误


@dataclass
class SamplingError:
    error_type: ErrorClass
    message: str
    status_code: int = 0


# 重试配置
RATE_LIMIT_RETRY_THRESHOLD = 3
MAX_RETRIES = 5


def retry_backoff_with_jitter(retry_count: int) -> float:
    """
    重试退避 + 抖动 (直接移植自 grok-build retry_backoff_with_jitter).
    
    策略: 
    - 第1次重试: ~2s
    - 第2次重试: ~4s (+ jitter)
    - 第3次重试: ~8s (+ jitter)
    - ...上限 30s
    - 每次添加随机抖动 (20%) 防止惊群效应
    """
    shift = max(0, retry_count - 1)
    base_ms = min(2000 * (2 ** shift), 30000)
    jitter_range = base_ms // 5  # 20%
    jitter = random.randint(-jitter_range, jitter_range)
    return (base_ms + jitter) / 1000.0


def classify_error(
    error: SamplingError,
    retry_count: int,
    max_retries: int = MAX_RETRIES,
) -> RetryDecision:
    """
    错误分类 (移植自 grok-build classify_error).
    
    返回应采取的决策。
    """
    if retry_count >= max_retries:
        return RetryDecision.FATAL

    if error.error_type == ErrorClass.STREAM:
        return RetryDecision.RETRY_WITH_NEW_CLIENT

    if error.error_type == ErrorClass.RATE_LIMIT:
        if retry_count < RATE_LIMIT_RETRY_THRESHOLD:
            return RetryDecision.RETRY
        return RetryDecision.FATAL

    if error.error_type == ErrorClass.AUTH:
        return RetryDecision.FATAL

    if error.error_type == ErrorClass.CONTEXT_OVERFLOW:
        return RetryDecision.FATAL

    if error.error_type == ErrorClass.TRANSIENT:
        return RetryDecision.RETRY

    return RetryDecision.FATAL


@dataclass
class Sampler:
    """推理采样器 — 管理重试、退避、预算"""

    max_retries: int = MAX_RETRIES
    retry_count: int = 0
    total_attempts: int = 0
    total_errors: int = 0

    def should_retry(self, error: SamplingError) -> tuple[bool, float | None]:
        """判断是否应重试，返回 (是否重试, 等待秒数)"""
        decision = classify_error(error, self.retry_count, self.max_retries)
        self.total_errors += 1
        self.retry_count += 1
        self.total_attempts += 1

        if decision in (RetryDecision.RETRY, RetryDecision.RETRY_WITH_NEW_CLIENT):
            wait = retry_backoff_with_jitter(self.retry_count)
            return True, wait

        return False, None

    def on_success(self):
        """成功时重置计数"""
        self.retry_count = 0
        self.total_attempts += 1

    def stats(self) -> dict:
        return {
            "retries": self.retry_count,
            "attempts": self.total_attempts,
            "errors": self.total_errors,
            "error_rate": (
                round(self.total_errors / self.total_attempts, 3)
                if self.total_attempts > 0 else 0
            ),
        }
