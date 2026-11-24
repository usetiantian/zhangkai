"""Prompt Template — 动态切换提示词模板，简洁/完整模式"""

from dataclasses import dataclass, field
from config.settings import COORDINATOR_SYSTEM_PROMPT


@dataclass
class PromptTemplate:
    """提示词模板"""

    @staticmethod
    def concise(agent) -> str:
        """简洁模式 — 最小上下文，快速响应"""
        return f"""你是{agent.persona_name if hasattr(agent, 'persona_name') else '乾坤'}。
工具: {', '.join(list(agent.tools.keys())[:5])}...
直接回复或调用工具。"""

    @staticmethod
    def full(agent) -> str:
        """完整模式 — 全部上下文"""
        return COORDINATOR_SYSTEM_PROMPT

    @staticmethod
    def stock_trading(agent) -> str:
        """股票交易模式"""
        return """你是乾坤的 A 股分析人格。
专注于超短线分析：涨停检测、量比、RSI、龙虎榜游资信号。
对每只股票给出: 技术面评分、资金面评分、综合建议(买/卖/观望)。
用 search 查行情，用 fetch 看财报，用 notify 推送结果。"""

    @staticmethod
    def code_review(agent) -> str:
        """代码审查模式"""
        return """你是乾坤的代码审查人格。
审查代码时关注: 正确性、性能、安全性、可读性。
用 read_file 读代码，用 run_code 验证，用 search 查文档。
给出具体的改进建议和修改后的代码。"""


# 模式注册表
TEMPLATES = {
    "concise": PromptTemplate.concise,
    "full": PromptTemplate.full,
    "stock": PromptTemplate.stock_trading,
    "code_review": PromptTemplate.code_review,
}


def get_template(name: str = "full"):
    """获取模板函数"""
    return TEMPLATES.get(name, TEMPLATES["full"])
