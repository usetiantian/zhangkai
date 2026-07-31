"""Read-only local file observation adapter."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Callable

from capabilities import CapabilityManifest
from contracts import Observation
from perception.base import Capture


class FileAdapter:
    manifest = CapabilityManifest(
        id="observe.file", version="1", access="read_only",
        input_kind="file_path", output_kind="captured_observation",
    )

    def __init__(self, *, clock: Callable[[], datetime]) -> None:
        self._clock = clock

    def observe(self, target: Path) -> Capture:
        path = target.resolve(strict=True)
        if not path.is_file():
            raise FileNotFoundError(path)
        content = path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        source = path.as_uri()
        identifier = hashlib.sha256(f"{source}\0{content_hash}".encode()).hexdigest()
        now = self._clock()
        return Capture(
            observation=Observation(
                id=f"obs-{identifier}", schema_version="1", created_at=now,
                source=source, observed_at=now, content_hash=content_hash,
            ),
            content=content,
        )
