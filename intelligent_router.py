"""Intelligent Model Router — 根据任务自动选择最优模型 (移植自 grok-build task_model_guidance)"""

import os
from dataclasses import dataclass, field
from enum import Enum
from agent.model_switch import AVAILABLE_MODELS
from agent.external_model import (
    ExternalModelProvider, BUILTIN_EXTERNAL_MODELS, ModelProvider, ModelConfig)


class TaskCategory(Enum):
    CHAT = "chat"              # 闲聊
    SEARCH = "search"          # 搜索
    CODE = "code"              # 代码
    ANALYSIS = "analysis"      # 分析
    REASONING = "reasoning"    # 深度推理
    STOCK = "stock"           # 股票
    FILE_OPS = "file_ops"     # 文件操作
    UNKNOWN = "unknown"


@dataclass
class ModelCandidate:
    """一个模型候选"""
    name: str
    provider: str              # local / deepseek / openai / ollama
    model_id: str = ""
    cost: str = "free"         # free / cheap / expensive
    speed: str = "fast"        # fast / medium / slow
    quality: str = "medium"    # low / medium / high
    suitable_for: list = field(default_factory=list)  # TaskCategory

    def to_dict(self) -> dict:
        return {
            "name": self.name, "provider": self.provider,
            "cost": self.cost, "speed": self.speed,
            "quality": self.quality,
        }


# 模型候选池
MODEL_POOL = {
    "qwen3-thinking": ModelCandidate(
        name="qwen3-thinking",
        provider="local",
        cost="free", speed="medium", quality="medium",
        suitable_for=[TaskCategory.CHAT, TaskCategory.SEARCH,
                      TaskCategory.FILE_OPS],
    ),
    "qwen2": ModelCandidate(
        name="qwen2",
        provider="local",
        cost="free", speed="fast", quality="low",
        suitable_for=[TaskCategory.CHAT, TaskCategory.FILE_OPS],
    ),
    "gpt-4o-mini": ModelCandidate(
        name="gpt-4o-mini",
        provider="openai", model_id="gpt-4o-mini",
        cost="cheap", speed="fast", quality="medium",
        suitable_for=[TaskCategory.CHAT, TaskCategory.CODE,
                      TaskCategory.SEARCH],
    ),
    "gpt-4o": ModelCandidate(
        name="gpt-4o",
        provider="openai", model_id="gpt-4o",
        cost="expensive", speed="medium", quality="high",
        suitable_for=[TaskCategory.CODE, TaskCategory.ANALYSIS,
                      TaskCategory.REASONING],
    ),
    "deepseek-v3": ModelCandidate(
        name="deepseek-v3",
        provider="deepseek", model_id="deepseek-chat",
        cost="cheap", speed="fast", quality="high",
        suitable_for=[TaskCategory.CHAT, TaskCategory.CODE,
                      TaskCategory.ANALYSIS, TaskCategory.STOCK,
                      TaskCategory.SEARCH, TaskCategory.FILE_OPS],
    ),
    "deepseek-r1": ModelCandidate(
        name="deepseek-r1",
        provider="deepseek", model_id="deepseek-reasoner",
        cost="cheap", speed="slow", quality="high",
        suitable_for=[TaskCategory.REASONING, TaskCategory.ANALYSIS,
                      TaskCategory.CODE],
    ),
}


def classify_task(user_input: str) -> TaskCategory:
    """分类任务类型"""
    text = user_input.lower()

    if any(w in text for w in ["股票", "a股", "涨停", "行情", "k线",
                                 "龙虎榜", "买入", "卖出", "持仓"]):
        return TaskCategory.STOCK
    if any(w in text for w in ["代码", "函数", "python", "编程", "写一个",
                                 "def ", "class ", "import ", "bug", "报错"]):
        return TaskCategory.CODE
    if any(w in text for w in ["搜索", "查一下", "搜一下", "找一下",
                                 "最新", "什么是", "怎么"]):
        return TaskCategory.SEARCH
    if any(w in text for w in ["分析", "对比", "比较", "评估",
                                 "为什么", "原因", "总结"]):
        return TaskCategory.ANALYSIS
    if any(w in text for w in ["推理", "逻辑", "证明", "如果",
                                 "是否", "合理"]):
        return TaskCategory.REASONING
    if any(w in text for w in ["文件", "目录", "读写", "保存",
                                 "打开", "创建文件夹"]):
        return TaskCategory.FILE_OPS

    return TaskCategory.CHAT


class IntelligentRouter:
    """
    智能路由 — 根据任务自动选择模型.
    
    策略 (移植自 grok-build task_model_guidance):
    - 简单任务 → 本地模型 (免费, 快)
    - 搜索/文件 → 本地或 cheap 外部
    - 代码/分析 → 高质量外部
    - 深度推理 → DeepSeek-R1
    - 本地模型弱项 → 自动升级到外部
    - 外部 API 不可用 → 回退到本地
    """

    def __init__(self):
        self.external = ExternalModelProvider()
        self.current_model: ModelCandidate | None = None
        self.fallback_chain: list[str] = []

    def select(self, user_input: str) -> ModelCandidate:
        """为当前任务选择最优模型"""
        task = classify_task(user_input)
        candidates = [
            c for c in MODEL_POOL.values()
            if task in c.suitable_for
        ]

        if not candidates:
            candidates = [MODEL_POOL["qwen3-thinking"]]

        # 排序: cost_rank + quality_rank + speed_rank
        def rank(c: ModelCandidate) -> int:
            cost_r = {"free": 3, "cheap": 2, "expensive": 1}.get(c.cost, 0)
            quality_r = {"high": 3, "medium": 2, "low": 1}.get(c.quality, 0)
            speed_r = {"fast": 3, "medium": 2, "slow": 1}.get(c.speed, 0)
            return cost_r + quality_r + speed_r

        candidates.sort(key=rank, reverse=True)

        # 检查 SelfModel: 如果本地模型在该域弱, 跳过
        try:
            from knowledge.self_model import get_scores
            scores = get_scores()
            domain_map = {
                TaskCategory.CHAT: "chat",
                TaskCategory.SEARCH: "search",
                TaskCategory.CODE: "code_gen",
                TaskCategory.ANALYSIS: "reasoning",
                TaskCategory.STOCK: "data_analysis",
            }
            domain = domain_map.get(task)
            if domain and scores.get(domain, 1.0) < 0.4:
                # 本地模型该域弱 — 排除本地候选
                candidates = [c for c in candidates
                              if c.provider != "local"]
        except Exception:
            pass

        # 检查 API 密钥
        for c in candidates:
            if c.provider == "local":
                break  # 本地总是可用
            if c.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
                continue
            if c.provider == "deepseek" and not os.environ.get("DEEPSEEK_API_KEY"):
                continue
            break

        # 回退: 如果没有外部密钥, 用本地
        best = candidates[0] if candidates else MODEL_POOL["qwen3-thinking"]
        if best.provider != "local":
            api_key_needed = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
            }.get(best.provider, "")
            if api_key_needed and not os.environ.get(api_key_needed):
                best = MODEL_POOL["qwen3-thinking"]  # 回退本地

        self.current_model = best
        self.fallback_chain.append(best.name)
        if len(self.fallback_chain) > 10:
            self.fallback_chain = self.fallback_chain[-10:]

        return best

    def get_current(self) -> ModelCandidate | None:
        return self.current_model

    def stats(self) -> dict:
        return {
            "current": self.current_model.name if self.current_model else "none",
            "provider": self.current_model.provider if self.current_model else "none",
            "recent_choices": self.fallback_chain[-5:],
        }


# 全局
_router: IntelligentRouter | None = None


def get_router() -> IntelligentRouter:
    global _router
    if _router is None:
        _router = IntelligentRouter()
    return _router
