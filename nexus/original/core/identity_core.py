"""
Nexus 身份权重核心 — 大脑

职责：
- 加载 Constitution + SOUL
- 接收感知输入，输出调度决策
- 知道我是谁、用户是谁、该做什么

通信：
- 发布: identity.decision（调度决策）
- 订阅: perception.input（用户输入）、memory.context（记忆上下文）
"""
import logging, json, os
from pathlib import Path

logger = logging.getLogger("nexus.identity")

# Constitution 默认值（不可变铁律）
DEFAULT_CONSTITUTION = {
    "A0": "守护用户利益",
    "A0.1": "禁止删除任何文件",
    "A1": "先备份再修改",
    "A2": "简洁优先",
    "A3": "闭环交付",
    "A4": "错误只犯一次",
    "A5": "主动汇报",
}

class IdentityCore:
    """身份核心。不是外挂prompt，是独立的神经决策层。"""

    def __init__(self):
        self.constitution = dict(DEFAULT_CONSTITUTION)
        self.soul = ""
        self.state = "initializing"
        self.decision_history = []

    def load_constitution(self, path: str = None):
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if ':' in line and line.strip().startswith(('A', 'A0')):
                        key, val = line.split(':', 1)
                        self.constitution[key.strip()] = val.strip()
        logger.info(f"Constitution: {len(self.constitution)} rules")

    def load_soul(self, path: str = None):
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.soul = f.read()
            logger.info(f"SOUL: {len(self.soul)} chars")

    def perceive(self, user_input: str, context: dict = None) -> dict:
        """接收用户输入，输出决策。"""
        self.state = "processing"

        # Constitution 检查
        for rule_id, rule_desc in self.constitution.items():
            if self._check_violation(user_input, rule_id, rule_desc):
                self.state = "idle"
                return {"action": "reject", "reason": f"违反{rule_id}: {rule_desc}"}

        action = self._classify_intent(user_input, context or {})
        self.decision_history.append(action)
        self.state = "idle"
        return action

    def _check_violation(self, text: str, rule: str, desc: str) -> bool:
        if "A0.1" in rule:
            dangerous = ["删除", "rm ", "rm -rf", "del ", "format", "抹掉"]
            return any(w in text for w in dangerous)
        return False

    def _classify_intent(self, text: str, context: dict) -> dict:
        """意图分类——规则版（后续升级 LLM 版）。"""
        if any(w in text for w in ["分析", "看看", "怎么看", "股票", "行情"]):
            return {"action": "analyze", "target": "stock_skill", "priority": 5}
        elif any(w in text for w in ["学习", "教我", "解释", "什么是"]):
            return {"action": "learn", "target": "auto_learner", "priority": 4}
        elif any(w in text for w in ["画", "设计", "cad", "图"]):
            return {"action": "skill", "target": "cad_skill", "priority": 5}
        elif any(w in text for w in ["搜索", "查", "找"]):
            return {"action": "search", "target": "chromadb", "priority": 3}
        else:
            return {"action": "chat", "target": "qwen", "priority": 2}

    def shutdown(self):
        self.state = "shutdown"
