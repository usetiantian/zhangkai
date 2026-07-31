"""Goal dependencies and explainable value-based ranking."""
from dataclasses import dataclass
from values import ValueSet

@dataclass(frozen=True)
class GoalCandidate:
    id: str
    description: str
    dependencies: tuple[str, ...]
    impacts: dict[str, float]
    def __post_init__(self):
        if not self.id.strip() or not self.description.strip(): raise ValueError("goal id and description required")
        if any(not -1.0 <= value <= 1.0 for value in self.impacts.values()): raise ValueError("impacts must be normalized")

@dataclass(frozen=True)
class GoalScore:
    goal_id: str
    score: float
    components: dict[str, float]

class GoalEngine:
    def __init__(self): self._goals: dict[str, GoalCandidate] = {}
    def add(self, goal: GoalCandidate):
        if goal.id in self._goals: raise ValueError("duplicate goal")
        self._goals[goal.id]=goal
    def ready(self, completed: set[str]) -> list[str]:
        return [goal.id for goal in self._goals.values() if set(goal.dependencies) <= completed]
    def rank(self, values: ValueSet) -> list[GoalScore]:
        scores=[]
        for goal in self._goals.values():
            components={name: impact * values.get(name) for name, impact in goal.impacts.items()}
            scores.append(GoalScore(goal.id, sum(components.values()), components))
        return sorted(scores, key=lambda item: (-item.score, item.goal_id))
