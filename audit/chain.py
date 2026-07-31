"""Append-only, tamper-evident audit event chain."""
from __future__ import annotations
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_GENESIS_HASH = "0" * 64
_SENSITIVE_MARKERS = (
    "token",
    "secret",
    "password",
    "apikey",
    "authorization",
)

class AuditError(ValueError):
    """Raised when an audit event is invalid or unsafe."""

@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    occurred_at: str
    event_type: str
    cause_id: str | None
    result: str
    data: dict[str, Any]
    previous_hash: str
    event_hash: str

def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

def _hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()

def _reject_sensitive(value: Any, path: str = "data") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower().replace("_", "").replace("-", "")
            if any(marker in normalized for marker in _SENSITIVE_MARKERS):
                raise AuditError(f"sensitive field forbidden: {path}.{key}")
            _reject_sensitive(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive(nested, f"{path}[{index}]")

class AuditChain:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def _raw_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def verify(self) -> bool:
        previous_hash = _GENESIS_HASH
        seen: set[str] = set()
        try:
            records = self._raw_records()
            for record in records:
                event_hash = record.pop("event_hash")
                if record["event_id"] in seen:
                    return False
                if record["previous_hash"] != previous_hash:
                    return False
                if _hash(record) != event_hash:
                    return False
                seen.add(record["event_id"])
                previous_hash = event_hash
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return True

    def append(
        self,
        event_id: str,
        occurred_at: datetime,
        event_type: str,
        cause_id: str | None,
        result: str,
        data: dict[str, Any],
    ) -> AuditEvent:
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise AuditError("occurred_at must be timezone-aware")
        if not all(value.strip() for value in (event_id, event_type, result)):
            raise AuditError("event id, type, and result are required")
        _reject_sensitive(data)
        if not self.verify():
            raise AuditError("existing audit chain is invalid")
        records = self._raw_records()
        if any(record["event_id"] == event_id for record in records):
            raise AuditError(f"duplicate event id: {event_id}")
        previous_hash = records[-1]["event_hash"] if records else _GENESIS_HASH
        unsigned = {
            "event_id": event_id,
            "occurred_at": occurred_at.isoformat(),
            "event_type": event_type,
            "cause_id": cause_id,
            "result": result,
            "data": data,
            "previous_hash": previous_hash,
        }
        event = AuditEvent(**unsigned, event_hash=_hash(unsigned))
        serialized = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event
