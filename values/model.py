"""Explicit value weights with provenance."""
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ValueWeight:
    name: str
    weight: float
    source: str
    calibrated_at: datetime
    def __post_init__(self):
        if not self.name.strip() or not self.source.strip(): raise ValueError("value name and source required")
        if not 0.0 <= self.weight <= 1.0: raise ValueError("weight must be normalized")
        if self.calibrated_at.tzinfo is None: raise ValueError("calibrated_at must be timezone-aware")

@dataclass(frozen=True)
class ValueSet:
    weights: tuple[ValueWeight, ...]
    def __post_init__(self):
        names=[item.name for item in self.weights]
        if len(names) != len(set(names)): raise ValueError("duplicate value weight")
    def get(self, name: str) -> float:
        return next((item.weight for item in self.weights if item.name == name), 0.0)
