"""Measured sustained-operation gates with explicit cycle thresholds."""
from __future__ import annotations
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

@dataclass(frozen=True)
class SoakReport:
    started_at: str
    ended_at: str
    duration_seconds: float
    required_cycles: int
    attempts: int
    verified: int
    unchanged: int
    failed: int
    recovered: int
    world_bytes_growth: int
    world_records_growth: int
    audit_events_growth: int
    disk_free_change: int

class SoakRunner:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        processor: Callable[[], str],
        world_path: Path,
        audit_path: Path,
        disk_path: Path,
        world_counter: Callable[[], int],
    ) -> None:
        self.clock = clock
        self.processor = processor
        self.world_path = world_path
        self.audit_path = audit_path
        self.disk_path = disk_path
        self.world_counter = world_counter

    @staticmethod
    def _size(path: Path) -> int:
        return path.stat().st_size if path.exists() else 0

    @staticmethod
    def _lines(path: Path) -> int:
        if not path.exists():
            return 0
        return len(path.read_text(encoding="utf-8").splitlines())

    def run(self, *, cycles: int) -> SoakReport:
        if cycles < 1:
            raise ValueError("cycles must be supplied and positive")
        started = self.clock()
        world_before = self._size(self.world_path)
        records_before = self.world_counter()
        audit_before = self._lines(self.audit_path)
        disk_before = shutil.disk_usage(self.disk_path).free
        counts = {"verified": 0, "unchanged": 0, "failed": 0, "recovered": 0}
        for _ in range(cycles):
            status = self.processor()
            if status not in counts:
                raise ValueError(f"unknown soak status: {status}")
            counts[status] += 1
        ended = self.clock()
        return SoakReport(
            started.isoformat(),
            ended.isoformat(),
            (ended - started).total_seconds(),
            cycles,
            cycles,
            counts["verified"],
            counts["unchanged"],
            counts["failed"],
            counts["recovered"],
            self._size(self.world_path) - world_before,
            self.world_counter() - records_before,
            self._lines(self.audit_path) - audit_before,
            shutil.disk_usage(self.disk_path).free - disk_before,
        )
