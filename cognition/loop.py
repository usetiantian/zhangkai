"""The first complete autonomous Shui cycle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from contracts import Plan, Prediction, Step
from execution import FileExecutor, verify_receipt
from goals import GoalCandidate, GoalEngine
from perception import FileAdapter
from provenance import EvidenceStore
from values import ValueSet
from world_model import WorldModel


@dataclass(frozen=True)
class CycleResult:
    status: str
    observation_id: str
    evidence_id: str
    receipt_verified: bool


class ShuiLoop:
    def __init__(
        self,
        state: Path,
        actions: Path,
        *,
        clock: Callable[[], datetime],
        values: ValueSet,
        candidates: tuple[GoalCandidate, ...],
    ) -> None:
        self.state = state
        self.actions = actions
        self.clock = clock
        self.values = values
        self.candidates = candidates
        self.evidence = EvidenceStore(state / "evidence")
        self.world = WorldModel(state / "world.db")
        self.adapter = FileAdapter(clock=clock)

    def tick(self, source: Path) -> CycleResult:
        ingested = self.evidence.ingest(self.adapter.observe(source))
        if not ingested.is_new:
            return CycleResult(
                "unchanged",
                ingested.observation.id,
                ingested.evidence.id,
                False,
            )

        self.world.put(ingested.evidence)
        goals = GoalEngine()
        for candidate in self.candidates:
            goals.add(candidate)
        if not self.candidates:
            raise ValueError("at least one candidate goal is required")
        selected = goals.rank(self.values)[0]

        now = self.clock()
        observation_id = ingested.observation.id
        step = Step(
            id=f"step-{observation_id}",
            schema_version="1",
            created_at=now,
            capability="write.verified-report",
            expected_result="verified report exists",
            recovery="restore previous report state",
        )
        plan = Plan(
            id=f"plan-{observation_id}",
            schema_version="1",
            created_at=now,
            goal_id=selected.goal_id,
            steps=(step,),
        )
        prediction = Prediction(
            id=f"pred-{observation_id}",
            schema_version="1",
            created_at=now,
            action_id=step.id,
            expected_outcome="verified report exists",
            verification_condition="report hash matches receipt",
        )
        payload = json.dumps(
            {
                "observation": ingested.observation.to_dict(),
                "evidence": ingested.evidence.to_dict(),
                "goal": selected.goal_id,
                "score": selected.score,
                "plan": plan.to_dict(),
                "prediction": prediction.to_dict(),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
        target = self.actions / f"{observation_id}.json"
        receipt = FileExecutor(self.actions).write(target, payload)
        verified = verify_receipt(receipt)
        return CycleResult(
            "verified" if verified else "failed",
            observation_id,
            ingested.evidence.id,
            verified,
        )
