"""Feedback Manager — 收集用户反馈，驱动改进"""

import json, time, threading
from pathlib import Path
from dataclasses import dataclass, field

FEEDBACK_DIR = Path("D:/qiankun/data/feedback")


@dataclass
class FeedbackEntry:
    """一条反馈"""
    session_id: str
    turn_input: str
    agent_output: str
    rating: int = 0        # 1-5
    comment: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        self.timestamp = time.time()


class FeedbackManager:
    """反馈管理器"""

    def __init__(self):
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        self.entries: list[FeedbackEntry] = []
        self._load()

    def _load(self):
        path = FEEDBACK_DIR / "feedback.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        d = json.loads(line)
                        self.entries.append(FeedbackEntry(**d))
                    except Exception:
                        pass

    def _save(self, entry: FeedbackEntry):
        path = FEEDBACK_DIR / "feedback.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "session_id": entry.session_id,
                "turn_input": entry.turn_input[:200],
                "agent_output": entry.agent_output[:200],
                "rating": entry.rating,
                "comment": entry.comment,
                "timestamp": entry.timestamp,
            }, ensure_ascii=False) + "\n")

    def record(self, session_id: str, user_input: str,
               agent_output: str, rating: int = 0,
               comment: str = "") -> FeedbackEntry:
        """记录反馈"""
        entry = FeedbackEntry(
            session_id=session_id, turn_input=user_input,
            agent_output=agent_output, rating=rating, comment=comment,
        )
        self.entries.append(entry)
        self._save(entry)

        # 如果是负面反馈 (rating <= 2)，自动标记为经验
        if rating <= 2:
            self._mark_negative_experience(entry)

        return entry

    def _mark_negative_experience(self, entry: FeedbackEntry):
        """负面反馈 → 自动记录为负面经验"""
        try:
            from learning.experience_bank import record
            record(
                entry.turn_input,
                {"action": "reply", "tool": "", "params": {}},
                entry.agent_output,
                domain="chat",
            )
            # 负面奖励
            from learning.experience_bank import get_unused, rate
            samples = get_unused(limit=1)
            if samples:
                rate(samples[0]["id"], -0.5)
        except Exception:
            pass

    def sync_loop(self):
        """后台同步循环 — 定期分析反馈"""
        def _loop():
            while True:
                time.sleep(600)  # 每 10 分钟
                self._analyze()

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def _analyze(self):
        """分析反馈趋势"""
        recent = [e for e in self.entries
                  if time.time() - e.timestamp < 3600]
        if not recent:
            return

        avg_rating = sum(e.rating for e in recent if e.rating > 0)
        rated = sum(1 for e in recent if e.rating > 0)

        if rated >= 5 and avg_rating / rated < 3.0:
            # 触发学习
            print(f"[反馈] 最近 {rated} 条评价均分 {avg_rating/rated:.1f}，建议训练")

    def stats(self) -> dict:
        """反馈统计"""
        recent = [e for e in self.entries
                  if time.time() - e.timestamp < 86400]
        rated = [e for e in recent if e.rating > 0]
        avg = (sum(e.rating for e in rated) / len(rated)
               if rated else 0)
        return {
            "total": len(self.entries),
            "today": len(recent),
            "avg_rating": round(avg, 2),
            "rated_count": len(rated),
        }


# 全局
_feedback_manager: FeedbackManager | None = None


def get_feedback_manager() -> FeedbackManager:
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager()
        _feedback_manager.sync_loop()
    return _feedback_manager
