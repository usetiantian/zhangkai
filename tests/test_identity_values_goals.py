import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from goals.engine import GoalCandidate, GoalEngine
from identity.store import Identity, IdentityStore
from values.model import ValueSet, ValueWeight

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)


class IdentityValuesGoalsTests(unittest.TestCase):
    def test_identity_versions_persist_and_latest_is_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IdentityStore(Path(directory) / "identity.db")
            first = Identity("shui", "1", ("learn from reality",), NOW)
            second = Identity("shui", "2", ("learn", "verify"), NOW)
            store.save(first); store.save(second)
            self.assertEqual(IdentityStore(store.database).latest(), second)
            self.assertEqual(store.get("1"), first)

    def test_weight_requires_declared_source(self):
        with self.assertRaises(ValueError):
            ValueWeight("truth", 1.0, "", NOW)

    def test_weight_outside_normalized_range_is_rejected(self):
        with self.assertRaises(ValueError):
            ValueWeight("truth", 1.1, "owner-decision", NOW)

    def test_goal_tree_respects_dependencies(self):
        engine = GoalEngine()
        engine.add(GoalCandidate("observe", "Observe reality", (), {"truth": 0.5}))
        engine.add(GoalCandidate("learn", "Learn from observation", ("observe",), {"truth": 1.0}))
        self.assertEqual(engine.ready(completed=set()), ["observe"])
        self.assertEqual(engine.ready(completed={"observe"}), ["observe", "learn"])

    def test_goal_ranking_is_explainable_and_changes_with_weights(self):
        engine = GoalEngine()
        engine.add(GoalCandidate("safe", "Safer path", (), {"safety": 1.0, "speed": 0.1}))
        engine.add(GoalCandidate("fast", "Faster path", (), {"safety": 0.1, "speed": 1.0}))
        safety = ValueSet((
            ValueWeight("safety", 1.0, "owner-decision", NOW),
            ValueWeight("speed", 0.1, "owner-decision", NOW),
        ))
        speed = ValueSet((
            ValueWeight("safety", 0.1, "owner-decision", NOW),
            ValueWeight("speed", 1.0, "owner-decision", NOW),
        ))
        safe_ranking = engine.rank(safety)
        fast_ranking = engine.rank(speed)
        self.assertEqual(safe_ranking[0].goal_id, "safe")
        self.assertEqual(fast_ranking[0].goal_id, "fast")
        self.assertEqual(set(safe_ranking[0].components), {"safety", "speed"})
        self.assertAlmostEqual(sum(safe_ranking[0].components.values()), safe_ranking[0].score)


if __name__ == "__main__":
    unittest.main()
