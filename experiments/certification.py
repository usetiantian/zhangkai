"""Durational certification gates for Shui with provider-trustable evidence."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

class Tier(str, Enum):
    CYCLES = "cycles"
    HOURS = "hours"
    DAYS = "days"

@dataclass(frozen=True)
class CertificationTier:
    tier: Tier
    threshold: int
    duration_seconds: int
    achieved: bool
    actual_cycles: int
    actual_seconds: float
    granted_at: str | None
    evidence_path: str | None

def evaluate(
    *,
    declared_tiers: list[dict],
    actual_cycles: int,
    actual_seconds: float,
    clock: Callable[[], datetime],
    evidence_writer,
) -> list[CertificationTier]:
    if actual_seconds < 0 or actual_cycles < 0:
        raise ValueError("actual measurement must be non-negative")
    now = clock().astimezone(timezone.utc)
    results: list[CertificationTier] = []
    for spec in declared_tiers:
        tier = Tier(spec["tier"])
        threshold = int(spec["threshold"])
        duration_seconds = int(spec.get("duration_seconds", 0))
        achieved = (
            (actual_cycles >= threshold)
            if tier is Tier.CYCLES
            else (actual_seconds >= duration_seconds)
        )
        granted_at = now.isoformat() if achieved else None
        evidence_path = None
        if achieved:
            evidence = {
                "tier": tier.value,
                "threshold": threshold,
                "duration_seconds": duration_seconds,
                "actual_cycles": actual_cycles,
                "actual_seconds": actual_seconds,
                "granted_at": granted_at,
            }
            evidence_path = evidence_writer(json.dumps(evidence, sort_keys=True))
        results.append(CertificationTier(
            tier=tier,
            threshold=threshold,
            duration_seconds=duration_seconds,
            achieved=achieved,
            actual_cycles=actual_cycles,
            actual_seconds=actual_seconds,
            granted_at=granted_at,
            evidence_path=evidence_path,
        ))
    return results
