"""Protocol-agnostic, per-source observation adapters."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from perception.web.adapter import HttpAdapter
from perception.rss.adapter import RssAdapter

@dataclass
class SourceObservation:
 source_id: str
 url: str
 observed_at: datetime
 content_hash: str
 changed: bool
 details: dict

class GenericHttp:
 def __init__(
  self,
  source_id: str,
  url: str,
  cache: Path,
  timeout_seconds: int,
  clock: Callable[[], datetime],
 ):
  self.id = source_id
  self.url = url
  self.alias = f"http:{source_id}"
  self._adapter = HttpAdapter(cache, clock=clock, timeout_seconds=timeout_seconds)
 def observe(self, *, clock: Callable[[], datetime]) -> SourceObservation:
  result = self._adapter.observe(self.url)
  return SourceObservation(
   self.id, self.url, result.observed_at, result.content_hash, result.changed,
   {"etag": result.etag},
  )

class GitHubTags(GenericHttp):
    protocol = "github_api"

class RssSource:
 def __init__(self, source_id: str, url: str, cache: Path, clock: Callable[[], datetime]):
  self.id = source_id
  self.url = url
  self.alias = f"rss:{source_id}"
  self._adapter = RssAdapter(cache, clock=clock)
 def observe(self, *, clock: Callable[[], datetime]) -> SourceObservation:
  result = self._adapter.observe(self.id, self.url)
  return SourceObservation(
   self.id, self.url, result.observed_at, result.content_hash, result.changed,
   {"items": [item.title for item in result.items]},
  )

def _cache_subdir(root: Path, source_id: str) -> Path:
  return root / hashlib.sha256(source_id.encode()).hexdigest()[:16]

def build_source(spec: dict, root: Path) -> GenericHttp | GitHubTags | RssSource:
  source_id = spec["id"]
  url = spec["url"]
  protocol = spec.get("protocol", "http")
  cache = _cache_subdir(root, source_id)
  if protocol == "http":
   timeout = int(spec.get("timeout_seconds", 10))
   return GenericHttp(source_id, url, cache, timeout, clock=lambda: datetime.now().astimezone())
  if protocol == "github_api":
   timeout = int(spec.get("timeout_seconds", 10))
   return GitHubTags(source_id, url, cache, timeout, clock=lambda: datetime.now().astimezone())
  if protocol == "rss":
   return RssSource(source_id, url, cache, clock=lambda: datetime.now().astimezone())
  raise ValueError(f"unsupported protocol: {protocol}")
