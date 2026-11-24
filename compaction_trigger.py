"""Compaction Trigger — 精确触发逻辑 (移植自 grok-build should_compact)"""

from dataclasses import dataclass
from enum import Enum


class CompactionMode(Enum):
    FULL_REPLACE = "full_replace"  # 完全替换式
    PARTIAL = "partial"            # 部分保留式


@dataclass
class CompactionConfig:
    """压缩配置"""
    enabled: bool = True
    mode: CompactionMode = CompactionMode.PARTIAL
    trigger_threshold_percent: int = 85     # 85% 触发
    min_steps_before_compact: int = 3       # Partial 模式下最小步数
    target_percent: int = 50                # 压缩到 50%


@dataclass
class CompactionTrigger:
    """触发信息"""
    last_prompt_tokens: int
    context_window: int
    percent: int
    step: int


def should_compact(
    config: CompactionConfig,
    last_prompt_tokens: int,
    context_window: int,
    current_step: int,
) -> CompactionTrigger | None:
    """
    判断是否需要压缩.
    
    移植自 grok-build should_compact:
    - enabled 检查
    - context_window > 0 检查  
    - Partial 模式下 min_steps 检查
    - token 阈值检查 (trigger_threshold_percent)
    """
    if not config.enabled:
        return None
    if context_window == 0:
        return None

    # Partial 模式: 跳过初始几步 (因为没多少内容可压缩)
    if (config.mode != CompactionMode.FULL_REPLACE
            and current_step < config.min_steps_before_compact):
        return None

    # Token 阈值检查
    threshold = (context_window * config.trigger_threshold_percent) // 100
    if last_prompt_tokens <= threshold:
        return None

    percent = min(
        (last_prompt_tokens * 100) // context_window,
        100
    )

    return CompactionTrigger(
        last_prompt_tokens=last_prompt_tokens,
        context_window=context_window,
        percent=percent,
        step=current_step,
    )
