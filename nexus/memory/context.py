"""
对话上下文管理器 — 让Nexus记住整段对话，不是每次从头开始

借鉴ClaudeCode的上下文管理: 短期窗口+摘要注入+压缩兜底
"""
import time, logging
from collections import deque, defaultdict

logger = logging.getLogger("nexus.context")

class ConversationContext:
    """多用户对话上下文管理。每个用户独立的对话历史。"""

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.conversations = defaultdict(lambda: deque(maxlen=max_history))
        self.summaries = defaultdict(str)  # 用户对话摘要(压缩后的)

    def add(self, user_id: str, role: str, content: str):
        """追加一轮对话。"""
        entry = {
            "role": role,       # "user" | "nexus"
            "content": content,
            "timestamp": time.time(),
        }
        self.conversations[user_id].append(entry)

        # 超过20轮生成摘要
        if len(self.conversations[user_id]) > 20:
            self._summarize(user_id)

    def get_context(self, user_id: str, max_turns: int = 10) -> str:
        """
        获取用户对话上下文——注入到Qwen prompt。
        返回格式化的上下文字符串。
        """
        conv = self.conversations[user_id]
        if not conv:
            return "[首次对话]"

        lines = []
        # 如果有摘要，先放摘要
        if self.summaries[user_id]:
            lines.append(f"[之前的对话摘要] {self.summaries[user_id]}")

        # 最近N轮完整对话
        for entry in list(conv)[-max_turns:]:
            role_name = "用户" if entry["role"] == "user" else "Nexus"
            content = entry["content"][:200]  # 每轮最多200字
            lines.append(f"{role_name}: {content}")

        return "\n".join(lines)

    def _summarize(self, user_id: str):
        """压缩对话为摘要。借鉴ClaudeCode的auto compact。"""
        conv = self.conversations[user_id]
        if len(conv) < 10:
            return

        # 提取关键话题
        topics = set()
        for entry in conv:
            text = entry.get("content", "")
            for kw in ["分析", "股票", "学习", "代码", "画图", "搜索", "删除", "配置", "训练"]:
                if kw in text:
                    topics.add(kw)

        self.summaries[user_id] = (
            f"已对话{len(conv)}轮。"
            f"涉及话题: {', '.join(topics) if topics else '通用'}。"
        )
        logger.debug(f"Summarized {user_id}: {self.summaries[user_id]}")

    def clear(self, user_id: str):
        """清除用户对话历史。"""
        self.conversations[user_id].clear()
        self.summaries[user_id] = ""

    def stats(self, user_id: str) -> dict:
        conv = self.conversations[user_id]
        return {
            "turns": len(conv),
            "has_summary": bool(self.summaries[user_id]),
            "last_turn": conv[-1]["content"][:50] if conv else "",
        }
