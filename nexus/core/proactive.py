"""
主动建议引擎 — 让Nexus在对话中主动想下一步

借鉴CC的行为模式:
- 完成一个任务后→建议相关的下一步
- 发现用户重复问→建议固化到技能
- 长时间不用某功能→建议清理
- 发现用户新的兴趣→建议学习相关技能
"""
import logging, time
from collections import defaultdict

logger = logging.getLogger("nexus.proactive")

class ProactiveEngine:
    """主动思考——不等用户开口，先想好建议。"""

    def __init__(self):
        self.user_patterns = defaultdict(lambda: defaultdict(int))  # {user: {action: count}}
        self.last_active = {}    # {user: timestamp}
        self.suggestions = defaultdict(list)

    def observe(self, user_id: str, action: str, intent: str = ""):
        """观察用户行为——积累模式数据。"""
        self.user_patterns[user_id][action] += 1
        self.last_active[user_id] = time.time()

    def think(self, user_id: str, current_intent: str = "") -> list:
        """
        基于用户模式主动思考建议。
        返回: [{type, suggestion, priority}]
        """
        suggestions = []
        patterns = self.user_patterns[user_id]

        # 1. 连续3次分析股票 → 建议设置定时扫描
        if patterns.get("analyze", 0) >= 3:
            suggestions.append({
                "type": "automation",
                "suggestion": "你已分析股票3次。要不要设置每天收盘自动扫描？",
                "priority": 5,
            })

        # 2. 聊天次数多但没用过技能 → 建议装技能
        if patterns.get("chat", 0) >= 10 and patterns.get("skill", 0) == 0:
            suggestions.append({
                "type": "discovery",
                "suggestion": "Nexus支持CAD画图、股票分析等技能。想看有什么吗？",
                "priority": 3,
            })

        # 3. 刚学完一个东西 → 建议深入
        if current_intent == "learn" and patterns.get("learn", 0) >= 2:
            suggestions.append({
                "type": "deepen",
                "suggestion": "学完这个，要不要做个小练习巩固一下？",
                "priority": 4,
            })

        # 4. 搜索多次但没保存 → 建议建立知识库
        if patterns.get("search", 0) >= 5:
            suggestions.append({
                "type": "organize",
                "suggestion": "你搜了5次了。要不要把这些整理成个人知识库？",
                "priority": 3,
            })

        # 5. 删除被Constitution拦截过 → 提醒约束存在
        if patterns.get("reject", 0) >= 1:
            suggestions.append({
                "type": "remind",
                "suggestion": "注意：Constitution保护你的数据不被删除。这是设计，不是bug。",
                "priority": 2,
            })

        self.suggestions[user_id] = suggestions
        return sorted(suggestions, key=lambda x: x["priority"], reverse=True)

    def should_suggest(self, user_id: str) -> bool:
        """判断此时是否应该主动说话。"""
        last = self.last_active.get(user_id, 0)
        suggestions = self.suggestions.get(user_id, [])
        # 有高优先级建议 或 沉默超过30秒
        return any(s["priority"] >= 4 for s in suggestions) or (time.time() - last > 30)

    def stats(self, user_id: str) -> dict:
        return {
            "actions": dict(self.user_patterns[user_id]),
            "suggestions": len(self.suggestions.get(user_id, [])),
        }
