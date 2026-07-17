"""
短期记忆 — 当前会话窗口（内存存储，进程退出丢失）

容量：最近20轮对话
用途：理解当前上下文的指代、维持连贯对话
"""
import logging
logger = logging.getLogger("nexus.memory.short")

class ShortTermMemory:
    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self.turns: list[dict] = []  # [{role, content, timestamp}]

    def add(self, role: str, content: str):
        self.turns.append({
            "role": role,       # "user" | "nexus"
            "content": content,
            "timestamp": __import__('time').time(),
        })
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        logger.debug(f"+turn [{role}] {content[:40]}... total={len(self.turns)}")

    def get_context(self, last_n: int = None) -> list:
        """获取最近N轮对话。"""
        n = last_n or self.max_turns
        return self.turns[-n:]

    def get_last_user_message(self) -> str:
        """获取用户最后一条消息。"""
        for turn in reversed(self.turns):
            if turn["role"] == "user":
                return turn["content"]
        return ""

    def clear(self):
        self.turns.clear()

    def summary(self) -> dict:
        return {
            "total_turns": len(self.turns),
            "last_turn": self.turns[-1]["content"][:60] if self.turns else "",
        }
