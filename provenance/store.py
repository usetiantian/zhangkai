"""Persistent, content-addressed evidence store."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from contracts import Evidence, Observation
from perception.base import Capture


@dataclass(frozen=True)
class IngestResult:
    observation: Observation
    evidence: Evidence
    is_new: bool


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw = root / "raw"
        self.database = root / "evidence.db"
        self.raw.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    evidence_id TEXT NOT NULL UNIQUE
                )
            """)

    def ingest(self, capture: Capture) -> IngestResult:
        observation = capture.observation
        digest = observation.content_hash.removeprefix("sha256:")
        if hashlib.sha256(capture.content).hexdigest() != digest:
            raise ValueError("capture content does not match observation hash")
        evidence_id = f"ev-{hashlib.sha256(observation.id.encode()).hexdigest()}"
        evidence = Evidence(
            id=evidence_id, schema_version="1", created_at=observation.created_at,
            observation_id=observation.id, source_uri=observation.source,
            content_hash=observation.content_hash,
        )
        snapshot = self.raw / digest
        snapshot.write_bytes(capture.content) if not snapshot.exists() else None
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO observations
                   (id, schema_version, created_at, source, observed_at, content_hash, evidence_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (observation.id, observation.schema_version,
                 observation.created_at.isoformat(), observation.source,
                 observation.observed_at.isoformat(), observation.content_hash,
                 evidence.id),
            )
            is_new = cursor.rowcount == 1
        return IngestResult(observation, evidence, is_new)

    def _evidence_row(self, evidence_id: str) -> tuple[str]:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT content_hash FROM observations WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        return row

    def snapshot(self, evidence_id: str) -> bytes:
        content_hash, = self._evidence_row(evidence_id)
        return (self.raw / content_hash.removeprefix("sha256:")).read_bytes()

    def verify(self, evidence_id: str) -> bool:
        content_hash, = self._evidence_row(evidence_id)
        expected = content_hash.removeprefix("sha256:")
        return hashlib.sha256(self.snapshot(evidence_id)).hexdigest() == expected

    def count(self) -> int:
        with closing(self._connect()) as connection, connection:
            return connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    def history(self, source: str) -> list[str]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT id FROM observations WHERE source = ? ORDER BY rowid", (source,)
            ).fetchall()
        return [row[0] for row in rows]
