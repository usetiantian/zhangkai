"""Versioned persistent identity and mission."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Identity:
    name: str
    version: str
    mission: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip() or not self.mission:
            raise ValueError("identity fields required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


class IdentityStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS identities(
                    version TEXT PRIMARY KEY,
                    name TEXT,
                    mission TEXT,
                    created_at TEXT
                )"""
            )

    def save(self, identity: Identity) -> None:
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO identities VALUES(?,?,?,?)",
                (
                    identity.version,
                    identity.name,
                    json.dumps(identity.mission),
                    identity.created_at.isoformat(),
                ),
            )

    def get(self, version: str) -> Identity:
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute(
                """SELECT name, version, mission, created_at
                   FROM identities WHERE version=?""",
                (version,),
            ).fetchone()
        if not row:
            raise KeyError(version)
        return Identity(
            row[0],
            row[1],
            tuple(json.loads(row[2])),
            datetime.fromisoformat(row[3]),
        )

    def latest(self) -> Identity:
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute(
                "SELECT version FROM identities ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        if not row:
            raise LookupError("no identity")
        return self.get(row[0])
