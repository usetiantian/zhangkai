"""Temporal, traceable world model storage."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from contracts import Claim, Conflict, Fact, Hypothesis, Record, record_from_dict
from datetime import timezone
from typing import Any


def _record_references_source(record, source: str) -> bool:
    data = record.to_dict()
    return any(source in str(value) for value in data.values())


def _ids_referenced_anywhere(value: object) -> set[str]:
    found: set[str] = set()
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            found.add(current)
        elif isinstance(current, (list, tuple, set)):
            stack.extend(current)
        elif isinstance(current, dict):
            stack.extend(current.values())
    return found


def _records_for_source(model: "WorldModel", source: str) -> set[str]:
    matched: set[str] = set()
    pending: list[str] = []
    for record in model.all():
        if _record_references_source(record, source):
            matched.add(record.id)
            pending.append(record.id)
    while pending:
        current = pending.pop()
        for record in model.all():
            if record.id in matched:
                continue
            if current in _ids_referenced_anywhere(record.to_dict()):
                matched.add(record.id)
                pending.append(record.id)
    return matched


class WorldModel:
    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    valid_from TEXT,
                    valid_until TEXT
                );
                CREATE TABLE IF NOT EXISTS sources (
                    uri TEXT PRIMARY KEY,
                    independence_group TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def put(self, record: Record, *, valid_from: datetime | None = None,
            valid_until: datetime | None = None) -> None:
        if valid_from and (valid_from.tzinfo is None or valid_from.utcoffset() is None):
            raise ValueError("valid_from must be timezone-aware")
        if valid_until and (valid_until.tzinfo is None or valid_until.utcoffset() is None):
            raise ValueError("valid_until must be timezone-aware")
        if valid_from and valid_until and valid_until < valid_from:
            raise ValueError("valid_until precedes valid_from")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
                (record.id, record.record_type, json.dumps(record.to_dict()),
                 valid_from.isoformat() if valid_from else None,
                 valid_until.isoformat() if valid_until else None),
            )

    def get(self, record_id: str) -> Record:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM records WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return record_from_dict(json.loads(row[0]))

    def all(self) -> list[Record]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT payload FROM records ORDER BY rowid").fetchall()
        return [record_from_dict(json.loads(row[0])) for row in rows]

    def query(
        self,
        *,
        record_type: str | None = None,
        source: str | None = None,
        contains: str | None = None,
        active_at: datetime | None = None,
        include_expired: bool = False,
    ) -> list[Record]:
        results = []
        for record in self.all():
            if record_type and type(record).__name__ != record_type:
                continue
            if source and record.id not in _records_for_source(self, source):
                continue
            if contains and contains.lower() not in json.dumps(record.to_dict()).lower():
                continue
            if active_at is not None and not include_expired:
                status = self.status_at(record.id, active_at)
                if status != "current":
                    continue
            results.append(record)
        return results

    def explain(self, record_id: str) -> dict[str, Any]:
        chain = self.trace(record_id)
        all_records = self.all()
        conflicts = [
            conflict.id
            for conflict in all_records
            if isinstance(conflict, Conflict) and record_id in conflict.record_ids
        ]
        validity = self.status_at(record_id, datetime.now(timezone.utc))
        return {
            "chain": [record.to_dict() for record in chain],
            "conflicts": conflicts,
            "validity": validity,
        }

    def trace(self, record_id: str) -> list[Record]:
        result: list[Record] = []
        seen: set[str] = set()

        def visit(identifier: str) -> None:
            if identifier in seen:
                return
            seen.add(identifier)
            record = self.get(identifier)
            result.append(record)
            references = (
                record.claim_ids if isinstance(record, Fact)
                else record.evidence_ids if isinstance(record, (Claim, Hypothesis))
                else ()
            )
            for reference in references:
                visit(reference)

        visit(record_id)
        return result

    def register_source(self, uri: str, independence_group: str) -> None:
        if not uri.strip() or not independence_group.strip():
            raise ValueError("source and independence group are required")
        with closing(self._connect()) as connection, connection:
            connection.execute("INSERT OR REPLACE INTO sources VALUES (?, ?)",
                               (uri, independence_group))

    def independent_source_count(self, uris: list[str]) -> int:
        if not uris:
            return 0
        placeholders = ",".join("?" for _ in uris)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT DISTINCT independence_group FROM sources WHERE uri IN ({placeholders})",
                uris,
            ).fetchall()
        return len(rows)

    def status_at(self, record_id: str, when: datetime) -> str:
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("query time must be timezone-aware")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT valid_from, valid_until FROM records WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        start = datetime.fromisoformat(row[0]) if row[0] else None
        end = datetime.fromisoformat(row[1]) if row[1] else None
        if start and when < start:
            return "not_yet_valid"
        if end and when > end:
            return "expired"
        return "current"
