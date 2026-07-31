"""Network cognitive runtime connected to durable strategy learning."""
from datetime import datetime
from pathlib import Path
from typing import Callable
from cognition.network_loop import NetworkLoop
from contracts import Prediction
from config import ShuiConfig
from goals import GoalCandidate
from learning import LearningStore, StrategyLearner
from values import ValueSet

class LearningRuntime:
    def __init__(
        self,
        state: Path,
        actions: Path,
        audit: Path,
        cache: Path,
        *,
        clock: Callable[[], datetime],
        values: ValueSet,
        candidates: tuple[GoalCandidate, ...],
        http_timeout_seconds: int,
        min_samples: int,
    ) -> None:
        self.learning = LearningStore(state / "learning.db")
        self.learner = StrategyLearner(
            self.learning,
            min_samples=min_samples,
        )
        self.loop = NetworkLoop(
            state,
            actions,
            audit,
            cache,
            clock=clock,
            values=values,
            candidates=candidates,
            http_timeout_seconds=http_timeout_seconds,
            before_action=self._predict,
            after_action=self._observe,
            preferred_strategy=self._preferred,
        )


    @classmethod
    def from_config(cls, config: ShuiConfig, *, clock: Callable[[], datetime]):
        values = ValueSet(config.values)
        candidates = tuple(
            GoalCandidate(
                goal.id,
                goal.description,
                goal.dependencies,
                goal.impacts,
            )
            for goal in config.goals
        )
        return cls(
            config.paths.state,
            config.paths.actions,
            config.paths.audit,
            config.paths.state / "http-cache",
            clock=clock,
            values=values,
            candidates=candidates,
            http_timeout_seconds=config.runtime.http_timeout_seconds,
            min_samples=config.runtime.learning_min_samples,
        )

    def _predict(self, prediction: Prediction, strategy: str) -> None:
        self.learning.predict(prediction.id, strategy, "success")

    def _observe(self, prediction: Prediction, result: str) -> None:
        self.learning.observe(prediction.id, result)

    def _preferred(self) -> str | None:
        experience = self.learner.best()
        return experience.strategy if experience else None

    def tick(self, url: str):
        return self.loop.tick(url)
