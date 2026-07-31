"""Measured repeated HTTP observation trials."""
from dataclasses import dataclass
from .adapter import HttpAdapter

@dataclass(frozen=True)
class StabilityReport:
    attempts: int
    changed: int
    unchanged: int
    failures: int

class StabilityMonitor:
    def __init__(self, adapter: HttpAdapter) -> None:
        self.adapter = adapter

    def run(self, url: str, *, cycles: int) -> StabilityReport:
        if cycles < 1:
            raise ValueError("cycles must be supplied and positive")
        changed = 0
        unchanged = 0
        failures = 0
        for _ in range(cycles):
            try:
                if self.adapter.observe(url).changed:
                    changed += 1
                else:
                    unchanged += 1
            except Exception:
                failures += 1
        return StabilityReport(cycles, changed, unchanged, failures)
