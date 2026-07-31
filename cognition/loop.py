"""The complete capture-to-verification Shui cycle."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from contracts import ActionReceipt, Plan, Prediction, Step, VerificationRecord
from execution import FileExecutor, verify_receipt
from goals import GoalCandidate, GoalEngine
from perception import Capture, FileAdapter
from provenance import EvidenceStore
from values import ValueSet
from world_model import WorldModel

@dataclass(frozen=True)
class CycleResult:
    status: str
    observation_id: str
    evidence_id: str
    receipt_verified: bool
    plan_id: str | None = None
    prediction_id: str | None = None
    receipt_id: str | None = None
    verification_id: str | None = None

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
        self.actions = actions
        self.clock = clock
        self.values = values
        self.candidates = candidates
        self.evidence = EvidenceStore(state / "evidence")
        self.world = WorldModel(state / "world.db")
        self.adapter = FileAdapter(clock=clock)

    def tick(self, source: Path) -> CycleResult:
        return self.process(self.adapter.observe(source))

    def process(self, capture: Capture) -> CycleResult:
        ingested = self.evidence.ingest(capture)
        observation_id = ingested.observation.id
        evidence_id = ingested.evidence.id
        if not ingested.is_new:
            return CycleResult("unchanged", observation_id, evidence_id, False)
        self.world.put(ingested.evidence)

        selected = self._select_goal()
        now = self.clock()
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
        payload = self._payload(ingested, selected, plan, prediction)
        target = self.actions / f"{observation_id}.json"
        file_receipt = FileExecutor(self.actions).write(target, payload)
        verified = verify_receipt(file_receipt)
        receipt = ActionReceipt(
            id=f"receipt-{observation_id}",
            schema_version="1",
            created_at=now,
            plan_id=plan.id,
            step_id=step.id,
            status="succeeded" if verified else "failed",
            observed_change=file_receipt.after_hash,
        )
        verification = VerificationRecord(
            id=f"verify-{observation_id}",
            schema_version="1",
            created_at=now,
            receipt_id=receipt.id,
            passed=verified,
            evidence_ids=(evidence_id,),
        )
        self.world.put(receipt)
        self.world.put(verification)
        return CycleResult(
            "verified" if verified else "failed",
            observation_id,
            evidence_id,
            verified,
            plan.id,
            prediction.id,
            receipt.id,
            verification.id,
        )

    def _select_goal(self):
        if not self.candidates:
            raise ValueError("at least one candidate goal is required")
        goals = GoalEngine()
        for candidate in self.candidates:
            goals.add(candidate)
        return goals.rank(self.values)[0]

    @staticmethod
    def _payload(ingested, selected, plan: Plan, prediction: Prediction) -> bytes:
        return json.dumps(
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
