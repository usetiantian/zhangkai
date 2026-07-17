"""摘要记忆 — 对话压缩结构化摘要"""
import time
class SummaryMemory:
    def __init__(self, max_summaries=50):
        self.summaries = []
        self.max_summaries = max_summaries

    def add(self, short_summary: str, key_points: list, source_turns: int):
        self.summaries.append({
            "summary": short_summary,
            "key_points": key_points,
            "turns_covered": source_turns,
            "timestamp": time.time(),
        })
        if len(self.summaries) > self.max_summaries:
            self.summaries = self.summaries[-self.max_summaries:]

    def get_recent(self, n=5) -> list:
        return self.summaries[-n:]

    def get_context_string(self, max_chars=500) -> str:
        """拼接最近摘要为上下文字符串。"""
        parts = []
        total = 0
        for s in reversed(self.summaries):
            text = f"[{s['turns_covered']}轮] {s['summary']}"
            if total + len(text) > max_chars: break
            parts.insert(0, text)
            total += len(text)
        return "\n".join(parts)
