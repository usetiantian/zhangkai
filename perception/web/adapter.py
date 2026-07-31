"""Cached conditional HTTP observation using only the standard library."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpObservation:
    url: str
    observed_at: datetime
    content: bytes
    content_hash: str
    changed: bool
    etag: str | None


class HttpAdapter:
    def __init__(
        self,
        cache: Path,
        *,
        clock: Callable[[], datetime],
        timeout_seconds: int,
    ) -> None:
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def observe(self, url: str) -> HttpObservation:
        key = hashlib.sha256(url.encode()).hexdigest()
        body_path = self.cache / f"{key}.body"
        meta_path = self.cache / f"{key}.json"
        meta = (
            json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_path.exists()
            else {}
        )
        headers = {"If-None-Match": meta["etag"]} if meta.get("etag") else {}

        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read()
                etag = response.headers.get("ETag")
                changed = True
        except HTTPError as error:
            if error.code != 304:
                raise
            content = body_path.read_bytes()
            etag = meta.get("etag")
            changed = False

        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        now = self.clock()
        if changed:
            body_path.write_bytes(content)
            metadata = {"url": url, "etag": etag, "content_hash": digest}
            meta_path.write_text(json.dumps(metadata), encoding="utf-8")
        return HttpObservation(url, now, content, digest, changed, etag)
