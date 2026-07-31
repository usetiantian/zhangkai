"""Caller-configured multi-timescale scheduler."""
from datetime import datetime, timedelta

class Scheduler:
    def __init__(self, intervals: dict[str, timedelta]) -> None:
        if not intervals or any(value <= timedelta(0) for value in intervals.values()):
            raise ValueError("positive intervals required")
        self.intervals = intervals
        self.last: dict[str, datetime] = {}

    def due(self, now: datetime) -> list[str]:
        return [
            name
            for name, interval in self.intervals.items()
            if name not in self.last or now - self.last[name] >= interval
        ]

    def mark(self, name: str, now: datetime) -> None:
        if name not in self.intervals:
            raise KeyError(name)
        self.last[name] = now
