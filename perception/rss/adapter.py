"""Read-only RSS 2.0 observation with per-source ETag caching."""
from __future__ import annotations
import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request,urlopen

@dataclass(frozen=True)
class RssItem:
 title: str
 link: str
 guid: str

@dataclass(frozen=True)
class RssObservation:
 source_id: str
 url: str
 observed_at: datetime
 content_hash: str
 changed: bool
 etag: str | None
 items: tuple[RssItem, ...]

class RssAdapter:
    def __init__(self, cache: Path, *, clock: Callable[[], datetime]) -> None:
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.clock = clock

    def _paths(self, source_id: str) -> tuple[Path, Path]:
        key = hashlib.sha256(source_id.encode()).hexdigest()
        return self.cache / f"{key}.body", self.cache / f"{key}.json"

    def observe(self, source_id: str, url: str) -> RssObservation:
        body_path, meta_path = self._paths(source_id)
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        headers = {"If-None-Match": meta["etag"]} if meta.get("etag") else {}
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=10) as response:
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
        items = self._parse(content)
        if changed:
            body_path.write_bytes(content)
            meta_path.write_text(json.dumps({"etag": etag}), encoding="utf-8")
        return RssObservation(source_id, url, self.clock(), digest, changed, etag, items)

    @staticmethod
    def _parse(content: bytes) -> tuple[RssItem, ...]:
        root = ET.fromstring(content)
        result = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link or title).strip()
            if title or link or guid:
                result.append(RssItem(title, link, guid))
        return tuple(result)
