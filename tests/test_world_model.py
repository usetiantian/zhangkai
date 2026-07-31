import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contracts import Claim, Conflict, Evidence, Fact, Hypothesis, Unknown
from world_model.store import WorldModel


NOW = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
BASE = {"schema_version": "1", "created_at": NOW}


class WorldModelTests(unittest.TestCase):
    def records(self):
        evidence = Evidence(
            id="ev-1", observation_id="obs-1", source_uri="https://a.example/item",
            content_hash="sha256:a", **BASE
        )
        claim = Claim(id="claim-1", statement="X is true", evidence_ids=(evidence.id,), **BASE)
        fact = Fact(id="fact-1", statement="X is true", claim_ids=(claim.id,), valid_at=NOW, **BASE)
        hypothesis = Hypothesis(
            id="hyp-1", statement="Y may follow X", evidence_ids=(evidence.id,),
            falsification="Observe not-Y after X", **BASE
        )
        unknown = Unknown(id="unknown-1", question="Does Y follow X?", blocking_goal_ids=("goal-1",), **BASE)
        conflict = Conflict(
            id="conflict-1", record_ids=(claim.id, "claim-2"),
            description="Sources disagree about X", **BASE
        )
        return evidence, claim, fact, hypothesis, unknown, conflict

    def test_types_remain_distinct_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "world.db"
            model = WorldModel(path)
            for record in self.records():
                model.put(record)
            reopened = WorldModel(path)
            self.assertEqual([type(r) for r in reopened.all()], [
                Evidence, Claim, Fact, Hypothesis, Unknown, Conflict,
            ])

    def test_fact_traces_back_to_claim_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            model = WorldModel(Path(directory) / "world.db")
            evidence, claim, fact, *_ = self.records()
            for record in (evidence, claim, fact):
                model.put(record)
            self.assertEqual([r.id for r in model.trace(fact.id)], [fact.id, claim.id, evidence.id])

    def test_source_independence_counts_groups_not_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            model = WorldModel(Path(directory) / "world.db")
            model.register_source("https://a.example/one", "publisher-a")
            model.register_source("https://mirror.example/copy", "publisher-a")
            model.register_source("https://b.example/one", "publisher-b")
            self.assertEqual(model.independent_source_count([
                "https://a.example/one", "https://mirror.example/copy", "https://b.example/one"
            ]), 2)

    def test_validity_is_evaluated_at_query_time(self):
        with tempfile.TemporaryDirectory() as directory:
            model = WorldModel(Path(directory) / "world.db")
            fact = self.records()[2]
            model.put(fact, valid_from=NOW, valid_until=NOW + timedelta(days=1))
            self.assertEqual(model.status_at(fact.id, NOW), "current")
            self.assertEqual(model.status_at(fact.id, NOW - timedelta(seconds=1)), "not_yet_valid")
            self.assertEqual(model.status_at(fact.id, NOW + timedelta(days=2)), "expired")

    def test_conflict_is_stored_without_overwriting_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            model = WorldModel(Path(directory) / "world.db")
            evidence, claim, _, _, _, conflict = self.records()
            opposite = Claim(id="claim-2", statement="X is false", evidence_ids=(evidence.id,), **BASE)
            for record in (evidence, claim, opposite, conflict):
                model.put(record)
            self.assertEqual(model.get(claim.id), claim)
            self.assertEqual(model.get(opposite.id), opposite)
            self.assertEqual(model.get(conflict.id), conflict)


if __name__ == "__main__":
    unittest.main()
