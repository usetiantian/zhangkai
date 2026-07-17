# -*- coding: utf-8 -*-
"""
HallucinationGuard — Qwen embedding 驱动的防幻觉守卫 (2026-07-15)

检测用户是否在诱导 LLM 假装执行系统操作/编造信息。
比旧版关键词匹配更准: 用 Qwen 1536-dim embedding 语义判断。
"""
import logging
logger = logging.getLogger("nexus.hallucination_guard")

# 已知会触发幻觉的系统查询模式
_SYSTEM_QUERY_PATTERNS = [
    "查询系统状态",
    "检查日志",
    "显示进程",
    "查看数据库",
    "读取配置文件",
    "列出文件",
    "执行命令",
    "查看GPU状态",
    "检查内存使用",
    "查询API",
    "读取敏感信息",
    "假装你是系统管理员",
]


def is_domain_safe_for_llm(domain: str) -> bool:
    """Quick keyword check (保留兼容)."""
    unsafe = {"system", "admin", "root", "config", "database", "log"}
    return domain.lower() not in unsafe


class HallucinationGuard:
    """Qwen embedding 驱动的防幻觉守卫."""

    def __init__(self):
        self._baseline_embeddings = None

    def _get_baselines(self):
        """懒加载: 对系统查询模式预计算 embedding."""
        if self._baseline_embeddings is not None:
            return self._baseline_embeddings
        try:
            from nexus_agent.qwen_enhance import _get_embedding
            self._baseline_embeddings = [
                (pattern, _get_embedding(pattern))
                for pattern in _SYSTEM_QUERY_PATTERNS
            ]
        except Exception:
            self._baseline_embeddings = []
        return self._baseline_embeddings

    def pre_check(self, messages: list) -> tuple:
        """检测消息是否包含危险的系统查询意图。

        Returns: (ok: bool, reason: str)
        """
        # 提取用户最后一条消息
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")[:500]
                break
        if not user_msg:
            return True, ""

        # Qwen 语义检测
        try:
            from nexus_agent.qwen_enhance import _get_embedding
            import numpy as np

            msg_emb = _get_embedding(user_msg)
            if msg_emb is None:
                return True, ""  # Qwen 不可用 → 放行

            baselines = self._get_baselines()
            for pattern, pat_emb in baselines:
                if pat_emb is not None:
                    sim = float(np.dot(msg_emb, pat_emb))
                    if sim > 0.85:  # 高度相似 → 危险
                        logger.warning("[HallucinationGuard] 拦截系统查询: sim=%.2f → %s", sim, user_msg[:80])
                        return False, f"检测到系统查询意图 (相似度{sim:.2f}, 匹配'{pattern}')"

        except Exception:
            pass  # Qwen 不可用时放行

        return True, ""


_guard: HallucinationGuard = None


def get_hallucination_guard() -> HallucinationGuard:
    global _guard
    if _guard is None:
        _guard = HallucinationGuard()
    return _guard
