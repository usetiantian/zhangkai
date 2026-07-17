# -*- coding: utf-8 -*-
"""
Qwen 嵌入增强 — 6个模块共享的语义评分工具 (2026-07-15)

使用 Qwen 1536-dim embedding 替代硬编码阈值。
仅在 Qwen 已加载时激活, 否则透明降级返回原值。
"""
import logging
import numpy as np

logger = logging.getLogger("nexus.qwen_enhance")


def _get_embedding(text: str):
    """获取 Qwen embedding (如果可用). 返回 None 表示未加载."""
    try:
        from nexus_agent.nexus_brain import get_brain
        brain = get_brain()
        if brain and brain.is_loaded:
            return brain.get_embedding(text)
    except Exception:
        pass
    return None


def semantic_similarity(text_a: str, text_b: str) -> float:
    a = _get_embedding(text_a)
    b = _get_embedding(text_b)
    if a is not None and b is not None:
        return max(0.0, min(1.0, float(np.dot(a, b))))
    return 0.5


def semantic_score(text: str, reference: str = "high quality content") -> float:
    return semantic_similarity(text, reference)


def classify_by_embedding(text: str, candidates: list) -> tuple:
    if not candidates:
        return (None, 0.0)
    emb = _get_embedding(text)
    if emb is None:
        return (candidates[0], 0.5)
    best, best_sim = candidates[0], -1.0
    for c in candidates:
        c_emb = _get_embedding(str(c))
        if c_emb is not None:
            sim = float(np.dot(emb, c_emb))
            if sim > best_sim:
                best_sim, best = sim, c
    return (best, max(0.0, min(1.0, best_sim)))


def anomaly_score(text: str, normal_baseline: str = "system operating normally") -> float:
    sim = semantic_similarity(text, normal_baseline)
    return round(1.0 - sim, 3)
