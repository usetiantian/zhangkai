"""Deterministic fault injection scenarios and recovery evidence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class FaultScenario:
    name: str
    action: Callable[[], object]
    expected_exception: type[BaseException]
    recovery_probe: Callable[[], bool]

@dataclass(frozen=True)
class FaultResult:
    name: str
    status: str
    contained: bool
    recovered: bool
    observed_exception: str | None

class FaultMatrix:
    def run(self, scenarios: list[FaultScenario]) -> list[FaultResult]:
        return [self._run_one(scenario) for scenario in scenarios]

    @staticmethod
    def _run_one(scenario: FaultScenario) -> FaultResult:
        status = "unexpected_success"
        contained = False
        observed = None
        try:
            scenario.action()
        except scenario.expected_exception as error:
            status = "expected_failure"
            contained = True
            observed = type(error).__name__
        except BaseException as error:
            status = "unexpected_failure"
            observed = type(error).__name__
        try:
            recovered = bool(scenario.recovery_probe())
        except BaseException:
            recovered = False
        return FaultResult(
            scenario.name,
            status,
            contained,
            recovered,
            observed,
        )
