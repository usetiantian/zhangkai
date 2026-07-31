import json
import unittest
from datetime import datetime, timezone

from contracts.models import (
    ActionReceipt,
    Claim,
    Evidence,
    Experience,
    Fact,
    Goal,
    Observation,
    Plan,
    Step,
    VerificationRecord,
    record_from_dict,
)


NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
BASE = {"schema_version": "1", "created_at": NOW}


class ContractTests(unittest.TestCase):
    def records(self):
        observation = Observation(
            id="obs-1", source="file:///news.txt", observed_at=NOW,
            content_hash="sha256:abc", **BASE
        )
        evidence = Evidence(
            id="ev-1", observation_id=observation.id,
            source_uri=observation.source, content_hash=observation.content_hash,
            **BASE
        )
        claim = Claim(
            id="claim-1", statement="A changed", evidence_ids=(evidence.id,), **BASE
        )
        fact = Fact(
            id="fact-1", statement=claim.statement,
            claim_ids=(claim.id,), valid_at=NOW, **BASE
        )
        goal = Goal(
            id="goal-1", description="Verify A",
            success_criteria=("A is observed",), status="candidate", **BASE
        )
        step = Step(
            id="step-1", capability="observe.file",
            expected_result="new observation", recovery="no state change", **BASE
        )
        plan = Plan(id="plan-1", goal_id=goal.id, steps=(step,), **BASE)
        receipt = ActionReceipt(
            id="receipt-1", plan_id=plan.id, step_id=step.id,
            status="succeeded", observed_change="obs-1 created", **BASE
        )
        verification = VerificationRecord(
            id="verify-1", receipt_id=receipt.id, passed=True,
            evidence_ids=(evidence.id,), **BASE
        )
        experience = Experience(
            id="exp-1", statement="File changes create observations",
            event_ids=(observation.id, receipt.id), **BASE
        )
        return (
            observation, evidence, claim, fact, goal, step, plan,
            receipt, verification, experience,
        )

    def test_all_records_round_trip_through_json(self):
        for record in self.records():
            encoded = json.dumps(record.to_dict())
            restored = record_from_dict(json.loads(encoded))
            self.assertEqual(restored, record)

    def test_records_are_immutable(self):
        record = self.records()[0]
        with self.assertRaises((AttributeError, TypeError)):
            record.id = "changed"

    def test_empty_required_text_is_rejected(self):
        with self.assertRaises(ValueError):
            Observation(
                id="", source="file:///x", observed_at=NOW,
                content_hash="sha256:x", **BASE
            )

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            Observation(
                id="obs", source="file:///x", observed_at=datetime(2026, 7, 31),
                content_hash="sha256:x", **BASE
            )

    def test_invalid_goal_status_is_rejected(self):
        with self.assertRaises(ValueError):
            Goal(
                id="goal", description="Do work",
                success_criteria=("verified",), status="invented", **BASE
            )

    def test_plan_requires_at_least_one_step(self):
        with self.assertRaises(ValueError):
            Plan(id="plan", goal_id="goal", steps=(), **BASE)

    def test_unknown_record_type_is_rejected(self):
        with self.assertRaises(ValueError):
            record_from_dict({"record_type": "NonexistentRecord"})


if __name__ == "__main__":
    unittest.main()
