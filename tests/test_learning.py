import tempfile, unittest
from pathlib import Path
from learning.engine import LearningStore, PredictionOutcome, StrategyLearner

class LearningTests(unittest.TestCase):
 def test_prediction_is_saved_before_outcome_and_survives_restart(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"learning.db"; store=LearningStore(db)
   store.predict("p1","strategy-a","success")
   store.observe("p1","failure")
   item=LearningStore(db).get("p1")
   self.assertEqual(item,PredictionOutcome("p1","strategy-a","success","failure"))
   self.assertFalse(item.matched)
 def test_outcome_without_prediction_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(KeyError): LearningStore(Path(d)/"x.db").observe("missing","success")
 def test_candidate_experience_requires_caller_supplied_sample_count(self):
  with tempfile.TemporaryDirectory() as d:
   store=LearningStore(Path(d)/"x.db")
   store.predict("a1","a","success");store.observe("a1","failure")
   learner=StrategyLearner(store,min_samples=2)
   self.assertIsNone(learner.best())
   store.predict("a2","a","success");store.observe("a2","failure")
   self.assertEqual(learner.best().strategy,"a")
 def test_later_evidence_can_change_learned_strategy(self):
  with tempfile.TemporaryDirectory() as d:
   store=LearningStore(Path(d)/"x.db")
   for i,result in enumerate(("success","failure")):
    store.predict(f"a{i}","a","success");store.observe(f"a{i}",result)
   for i,result in enumerate(("success","success")):
    store.predict(f"b{i}","b","success");store.observe(f"b{i}",result)
   learner=StrategyLearner(store,min_samples=2)
   choice=learner.best()
   self.assertEqual(choice.strategy,"b");self.assertEqual(choice.success_rate,1.0)
   self.assertEqual(learner.improvement_over("a"),0.5)

if __name__=="__main__":unittest.main()
