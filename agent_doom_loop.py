"""Doom Loop Detection — 检测模型死循环并自动恢复"""

import time
from dataclasses import dataclass, field


@dataclass
class DoomLoopDetector:
    """死循环检测器"""

    max_consecutive_same: int = 5       # 连续相同输出次数
    max_turns_without_progress: int = 10  # 无进展的最大轮次
    history: list = field(default_factory=list)
    warnings: int = 0
    recoveries: int = 0

    def feed(self, output: str) -> dict:
        """喂入一次输出，检测是否陷入死循环"""
        self.history.append({
            "output": output[:200],
            "time": time.time(),
        })
        if len(self.history) > 50:
            self.history = self.history[-50:]

        result = {"doom_loop": False, "action": "none"}

        # 检测 1: 连续相同输出
        if len(self.history) >= self.max_consecutive_same:
            recent = [h["output"] for h in self.history[-self.max_consecutive_same:]]
            if len(set(recent)) == 1:
                result = {
                    "doom_loop": True,
                    "action": "reset_context",
                    "reason": f"连续 {self.max_consecutive_same} 次相同输出",
                }

        # 检测 2: 长时间无进展
        if len(self.history) >= self.max_turns_without_progress:
            recent = self.history[-self.max_turns_without_progress:]
            if all(len(h["output"]) < 50 for h in recent):
                result = {
                    "doom_loop": True,
                    "action": "force_stop",
                    "reason": f"{self.max_turns_without_progress} 轮无实质进展",
                }

        if result["doom_loop"]:
            self.warnings += 1

        return result

    def recovery_action(self, detection: dict) -> str:
        """返回恢复提示"""
        if detection["action"] == "reset_context":
            self.recoveries += 1
            return ("检测到重复输出。我重新整理一下思路...\n"
                    f"({detection['reason']})")
        if detection["action"] == "force_stop":
            self.recoveries += 1
            return ("我似乎陷入了循环。让我换一种方式思考这个问题。\n"
                    f"({detection['reason']})")
        return ""

    def reset(self):
        self.history = []

    def stats(self) -> dict:
        return {
            "warnings": self.warnings,
            "recoveries": self.recoveries,
            "history_size": len(self.history),
        }
