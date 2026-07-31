"""Evidence-driven source and event attention."""
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class AttentionWeights:
    relevance: float
    stability: float
    traceability: float
    verifiability: float

    def __post_init__(self) -> None:
        values = (
            self.relevance,
            self.stability,
            self.traceability,
            self.verifiability,
        )
        if any(not 0 <= value <= 1 for value in values) or sum(values) == 0:
            raise ValueError("valid external weights required")

@dataclass(frozen=True)
class SourceCandidate:
    id: str
    relevance: float
    stability: float
    traceability: float
    verifiability: float

def attention_score(
    relevance: float,
    stability: float,
    traceability: float,
    verifiability: float,
    weights: AttentionWeights,
) -> float:
    total = sum((weights.relevance, weights.stability, weights.traceability, weights.verifiability))
    weighted = (
        relevance * weights.relevance
        + stability * weights.stability
        + traceability * weights.traceability
        + verifiability * weights.verifiability
    )
    return weighted / total

class SourceSelector:
    def __init__(self, weights: AttentionWeights) -> None:
        self.weights = weights

    def rank(self, candidates: Iterable[SourceCandidate]) -> list[SourceCandidate]:
        return sorted(
            candidates,
            key=lambda candidate: (
                -attention_score(
                    candidate.relevance,
                    candidate.stability,
                    candidate.traceability,
                    candidate.verifiability,
                    self.weights,
                ),
                candidate.id,
            ),
        )
