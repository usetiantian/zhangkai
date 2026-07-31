"""Shared perception adapter protocol."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from capabilities import CapabilityManifest
from contracts import Observation


@dataclass(frozen=True)
class Capture:
    observation: Observation
    content: bytes


class ObservationAdapter(Protocol):
    manifest: CapabilityManifest

    def observe(self, target: Path) -> Capture: ...
