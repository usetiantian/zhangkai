"""Heartbeat, per-source checkpoints, and failure isolation."""
from __future__ import annotations
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence
from audit.chain import AuditChain

@dataclass(frozen=True)
class CycleReport:
    completed: int
    failed: int

class RecoveryCoordinator:
    def __init__(
        self,
        checkpoint_path: Path,
        heartbeat_path: Path,
        audit: AuditChain,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
        processor: Callable[[str], str],
    ) -> None:
        self.checkpoint_path = checkpoint_path
        self.heartbeat_path = heartbeat_path
        self.audit = audit
        self.clock = clock
        self.id_factory = id_factory
        self.processor = processor

    @staticmethod
    def _read(path: Path, fallback: dict[str, object]) -> dict[str, object]:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write(path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def checkpoint(self) -> dict[str, object]:
        return self._read(
            self.checkpoint_path,
            {"next_index": 0, "cycles_completed": 0},
        )

    def heartbeat(self) -> dict[str, object]:
        return self._read(
            self.heartbeat_path,
            {"status": "never_started", "cycles_completed": 0},
        )

    def _beat(self, status: str, cycles: int, source: str | None) -> None:
        self._write(
            self.heartbeat_path,
            {
                "observed_at": self.clock().isoformat(),
                "status": status,
                "cycles_completed": cycles,
                "last_source": source,
            },
        )

    def _event(
        self,
        event_type: str,
        result: str,
        data: dict[str, object],
    ) -> None:
        self.audit.append(
            self.id_factory(),
            self.clock(),
            event_type,
            None,
            result,
            data,
        )

    def run_once(self, sources: Sequence[str]) -> CycleReport:
        state = self.checkpoint()
        start = int(state["next_index"])
        cycles = int(state["cycles_completed"])
        completed = 0
        failed = 0
        self._beat("running", cycles, None)
        for index in range(start, len(sources)):
            source = sources[index]
            self._beat("running", cycles, source)
            try:
                self.processor(source)
                completed += 1
                self._event("source.completed", "success", {"source": source})
            except Exception as error:
                failed += 1
                self._event(
                    "source.failed",
                    "failure",
                    {"source": source, "error_type": type(error).__name__},
                )
                self._event("cycle.recovered", "success", {"source": source})
            self._write(
                self.checkpoint_path,
                {"next_index": index + 1, "cycles_completed": cycles},
            )
        cycles += 1
        self._write(
            self.checkpoint_path,
            {"next_index": 0, "cycles_completed": cycles},
        )
        self._beat("idle", cycles, sources[-1] if sources else None)
        return CycleReport(completed, failed)

    def audit_records(self) -> list[dict[str, object]]:
        if not self.audit.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.audit.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
