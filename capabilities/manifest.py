"""Machine-readable capability declarations."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CapabilityManifest:
    id: str
    version: str
    access: str
    input_kind: str
    output_kind: str
