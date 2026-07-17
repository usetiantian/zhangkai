# -*- coding: utf-8 -*-
"""StrategyLearner — 从数据中学策略, 不拍脑袋 (v18.5n)

查询 ExperienceBank → 聚合各域各策略效果 → 更新子系统权重 → 分配探索配额。

被 heartbeat 每30min调用。
"""

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


async def strategy_audit() -> Dict:
    """从 ExperienceBank 学习策略效果, 自动更新子系统参数。

    Returns:
        {strategies_updated, subsystems_affected, top_strategies, recommendations}
    """
    result = {
        "strategies_updated": 0,
        "subsystems_affected": [],
        "top_strategies": [],
        "recommendations": [],
    }

    # 1. 读取近期策略记录
    try:
        from nexus_agent.experience_bank import get_experience_bank
        bank = get_experience_bank()
        recents = bank.get_recent(days=7)
    except Exception:
        logger.debug("[StrategyLearner] ExperienceBank unavailable", exc_info=True)
        return result

    if len(recents) < 10:
        result["recommendations"].append("数据不足 (<10条), 继续积累")
        return result

    # 2. 聚合: (domain, strategy) → 平均效果
    strategy_scores: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for exp in recents:
        domain = _infer_domain(exp)
        strategy = _infer_strategy(exp)
        if domain == "unknown" or strategy == "unknown":
            continue
        score = getattr(exp, 'significance', 0.5)
        if getattr(exp, 'valence', 0) > 0:
            strategy_scores[(domain, strategy)].append(score)

    if not strategy_scores:
        result["recommendations"].append("无有效策略记录")
        return result

    # 3. 计算有效性 (样本折扣)
    effectiveness = {}
    for (domain, strategy), scores in strategy_scores.items():
        avg = sum(scores) / len(scores)
        discount = min(1.0, len(scores) / 5.0)  # <5个样本打折
        effectiveness[(domain, strategy)] = avg * discount

    # 4. 排名
    ranked = sorted(effectiveness.items(), key=lambda x: -x[1])
    result["top_strategies"] = [
        {"domain": d, "strategy": s, "effectiveness": round(e, 3)}
        for (d, s), e in ranked[:5]
    ]

    # 5. 应用到各子系统
    strategies_applied = 0

    # 5a. ASTMutation 适应度
    try:
        from nexus_agent.ast_mutation_engine import get_mutation_engine
        engine = get_mutation_engine()
        for (domain, strategy), eff in effectiveness.items():
            if domain in ('pattern_completion', 'self_modification', 'knowledge_graph'):
                engine.record_fitness(domain, strategy, eff - 0.5)
                strategies_applied += 1
        if strategies_applied > 0:
            result["subsystems_affected"].append("ast_mutation")
    except Exception:
        logger.debug("AST mutation update skipped", exc_info=True)

    # 5b. 探索配额
    explored = set(effectiveness.keys())
    all_domains = {'pattern_completion', 'self_modification', 'knowledge_graph'}
    all_strategies = ['llm_guided', 'rename_variable', 'extract_function',
                       'swap_operators', 'add_type_hint', 'change_constant']
    explorable = [(d, s) for d in all_domains for s in all_strategies
                  if (d, s) not in explored]
    if explorable:
        result["recommendations"].append(
            f"探索配额: {len(explorable)} 组未测试 (建议分配15%预算)"
        )

    # 6. 记录审计结果
    try:
        bank.add_content(
            content=f"StrategyAudit: {strategies_applied} weights, "
                   f"top={ranked[0][0][1] if ranked else 'none'}:{ranked[0][1]:.2f}",
            source="strategy_learner",
            topic="meta_learning",
        )
    except Exception:
        logger.debug("audit recording skipped", exc_info=True)

    result["strategies_updated"] = strategies_applied
    if strategies_applied > 0:
        logger.info("[StrategyLearner] %d weights updated, top: %s",
                   strategies_applied, result["top_strategies"][:2])

    return result


def _infer_domain(exp) -> str:
    """从经验中推断 domain。"""
    tags = getattr(exp, 'tags', [])
    if tags:
        return tags[0]
    content = getattr(exp, 'content', '')
    for d in ['pattern_completion', 'self_modification', 'knowledge_graph',
              'programming', 'math', 'tcm', 'finance', 'ai']:
        if d in content.lower():
            return d
    return "unknown"


def _infer_strategy(exp) -> str:
    """从经验中推断 strategy。"""
    tags = getattr(exp, 'tags', [])
    if len(tags) > 1:
        return tags[1]
    content = (getattr(exp, 'content', '') + ' ' +
              ','.join(getattr(exp, 'tags', []))).lower()
    for s in ['llm_guided', 'rename_variable', 'extract_function', 'swap_operators',
              'add_type_hint', 'change_constant', 'restart', 'patch', 'rollback']:
        if s in content:
            return s
    return "unknown"
