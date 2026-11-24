"""Chat State — 精确 token 估算 + 预算适配 (移植自 grok-build fit_conversation_to_budget)"""

import tiktoken
from dataclasses import dataclass, field
from enum import Enum

# Token 估算器
try:
    _encoder = tiktoken.get_encoding("cl100k_base")
except Exception:
    _encoder = None


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"


@dataclass
class ConversationItem:
    role: Role
    content: str
    tool_name: str = ""
    tool_call_id: str = ""


def estimate_tokens(text: str) -> int:
    """估算 token 数 (cl100k_base)"""
    if _encoder:
        return len(_encoder.encode(text))
    # 回退: 简单估算 (1 token ≈ 4 chars for English, ≈ 2 chars for Chinese)
    return max(1, len(text) // 3)


def estimate_item_tokens(item: ConversationItem) -> int:
    """估算单条消息的 token 数"""
    base = estimate_tokens(item.content)
    # 消息格式开销
    overhead = 4  # role tag
    if item.tool_name:
        overhead += estimate_tokens(item.tool_name) + 2
    return base + overhead


def fit_conversation_to_budget(
    conversation: list[ConversationItem],
    max_tokens: int,
) -> list[ConversationItem]:
    """
    缩减对话以适应 token 预算 (直接移植自 grok-build).
    
    策略:
    1. 保留 System prompt
    2. 从尾部开始保留最近的消息 (逐条累加)
    3. 从不切断 tool-result 配对
    4. 如果中间不够，从头部丢掉旧消息
    """
    total = sum(estimate_item_tokens(item) for item in conversation)
    if total <= max_tokens:
        return conversation

    head = []
    body = list(conversation)

    # 永远保留 System prompt
    if body and body[0].role == Role.SYSTEM:
        head.append(body.pop(0))

    # 从尾部往前扫描，保留尽可能多的最近消息
    budget = max_tokens - sum(estimate_item_tokens(item) for item in head)
    remaining = budget
    start = len(body)

    for i in range(len(body) - 1, -1, -1):
        cost = estimate_item_tokens(body[i])
        if cost > remaining:
            break
        remaining -= cost
        start = i

    # 跳过孤立的 tool_result (必须和前面的 user/assistant 配对)
    while start < len(body) and body[start].role == Role.TOOL_RESULT:
        start += 1

    if start < len(body):
        head.extend(body[start:])

    return head


@dataclass
class ChatState:
    """会话状态跟踪 — token 计数 + 自动压缩触发"""

    messages: list[ConversationItem] = field(default_factory=list)
    context_window: int = 4096
    compaction_threshold: float = 0.85  # 85% 时触发压缩
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    compaction_count: int = 0

    def add_message(self, item: ConversationItem):
        """添加消息并更新 token 计数"""
        self.messages.append(item)
        self.total_input_tokens += estimate_item_tokens(item)

    def add_user(self, content: str):
        self.add_message(ConversationItem(role=Role.USER, content=content))

    def add_assistant(self, content: str):
        self.add_message(ConversationItem(role=Role.ASSISTANT, content=content))
        self.total_output_tokens += estimate_tokens(content)

    def add_tool_result(self, content: str, tool_name: str = ""):
        self.add_message(ConversationItem(
            role=Role.TOOL_RESULT, content=content, tool_name=tool_name))

    def current_tokens(self) -> int:
        """当前总 token 数"""
        return sum(estimate_item_tokens(m) for m in self.messages)

    def needs_compaction(self) -> bool:
        """是否需要压缩"""
        return self.current_tokens() > self.context_window * self.compaction_threshold

    def compact(self, target_tokens: int = None) -> int:
        """
        执行压缩。
        返回保留的消息数。
        """
        if target_tokens is None:
            target_tokens = int(self.context_window * 0.5)  # 压缩到 50%

        old_count = len(self.messages)
        self.messages = fit_conversation_to_budget(self.messages, target_tokens)
        self.compaction_count += 1

        return len(self.messages)

    def stats(self) -> dict:
        return {
            "messages": len(self.messages),
            "current_tokens": self.current_tokens(),
            "context_window": self.context_window,
            "usage_pct": round(self.current_tokens() / self.context_window * 100, 1),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "compactions": self.compaction_count,
            "needs_compaction": self.needs_compaction(),
        }
