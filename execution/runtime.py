"""Idempotent task leases and verifiable file execution."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class TaskStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS tasks(
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    status TEXT,
                    owner TEXT,
                    lease_until TEXT
                )"""
            )

    def create(self, task_id: str, key: str) -> str:
        with closing(sqlite3.connect(self.database)) as connection, connection:
            row = connection.execute(
                "SELECT id FROM tasks WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if row:
                return row[0]
            connection.execute(
                "INSERT INTO tasks VALUES(?,?,'pending',NULL,NULL)",
                (task_id, key),
            )
            return task_id

    def acquire(
        self,
        task_id: str,
        owner: str,
        until: datetime,
        now: datetime,
    ) -> bool:
        if any(value.tzinfo is None for value in (until, now)):
            raise ValueError("lease times require timezone")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            cursor = connection.execute(
                """UPDATE tasks
                   SET status='running', owner=?, lease_until=?
                   WHERE id=? AND (lease_until IS NULL OR lease_until<=?)""",
                (owner, until.isoformat(), task_id, now.isoformat()),
            )
            return cursor.rowcount == 1

    def counts(self) -> dict[str, int]:
        with closing(sqlite3.connect(self.database)) as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) FROM tasks GROUP BY status"
            ).fetchall()
        return {status: count for status, count in rows}


@dataclass(frozen=True)
class FileReceipt:
    target: Path
    before: bytes | None
    after_hash: str


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FileExecutor:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _target(self, target: Path) -> Path:
        path = target.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("target escapes execution root")
        return path

    def write(self, target: Path, content: bytes) -> FileReceipt:
        path = self._target(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        before = path.read_bytes() if path.exists() else None
        file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(file_descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return FileReceipt(path, before, _hash(content))

    def rollback(self, receipt: FileReceipt) -> None:
        if receipt.before is None:
            receipt.target.unlink(missing_ok=True)
        else:
            self.write(receipt.target, receipt.before)


def verify_receipt(receipt: FileReceipt) -> bool:
    return (
        receipt.target.is_file()
        and _hash(receipt.target.read_bytes()) == receipt.after_hash
    )
