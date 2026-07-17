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
        """接收用户输入，按六级优先级输出决策。

        优先级(借鉴ClaudeCode):
        1. OVERRIDE — A0.1禁止删除(任何层级不可覆盖)
        2. COORDINATOR — 身份核心调度
        3. AGENT — 当前激活技能指令
        4. CUSTOM — 用户自定义规则
        5. DEFAULT — Nexus出厂默认
        6. APPENDING — 动态上下文
        """
        self.state = "processing"
        ctx = context or {}

        # 第1优先级: OVERRIDE — Constitution A0.1
        for rule_id, rule_desc in self.constitution.items():
            if self._check_violation(user_input, rule_id, rule_desc):
                self.state = "idle"
                return {"action": "reject", "reason": f"违反{rule_id}: {rule_desc}", "priority_level": 1}

        # 第2优先级: COORDINATOR — 检查是否有活跃的调度指令
        if ctx.get("active_plan"):
            return {"action": "continue_plan", "target": ctx["active_plan"], "priority_level": 2}

        # 第3-4优先级: AGENT/CUSTOM — 意图分类
        action = self._classify_intent(user_input, ctx)
        action["priority_level"] = 3

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

        # 尝试深度推理(如果模型可用)
        deep = self._deep_think(text, context)
        if deep:
            return deep

        # 降级: 规则匹配
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

    def _deep_think(self, text: str, context: dict) -> dict:
        """
        深度推理——用Qwen真正理解用户意图。
        借鉴ClaudeCode的"模型即理解引擎"设计哲学。
        输出JSON: {"action":"analyze|learn|skill|search|chat","target":"...","priority":1-5}
        """
        if not hasattr(self, '_generate') or not self._generate:
            return None

        try:
            prompt = (
                "你是一个意图分类器。分析用户输入，输出JSON格式的决策。\n"
                "可能的action: analyze(分析事物), learn(学习知识), skill(使用技能), "
                "search(搜索信息), chat(闲聊)\n"
                "priority: 1(低)-5(高)\n"
                "只输出JSON，不要解释。\n\n"
                f"用户: {text}\n"
                "输出: "
            )
            raw = self._generate(prompt, 80)
            import json
            # 尝试从输出中提取JSON
            if "{" in raw and "}" in raw:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                data = json.loads(raw[start:end])
                data.setdefault("priority", 3)
                return data
        except Exception:
            pass
        return None

    def attach_model(self, generate_fn):
        """注入模型推理函数——让身份核心真正思考。"""
        self._generate = generate_fn

    def shutdown(self):
        self.state = "shutdown"
