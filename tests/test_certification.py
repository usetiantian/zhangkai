import tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from experiments.certification import evaluate, Tier

class CertificationTests(unittest.TestCase):
 def test_cycles_tier_is_granted_only_when_threshold_is_reached(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   writer=lambda body:paths.append(body) or f"{Path(d)/'cert'}/{len(paths)}.json"
   results=evaluate(declared_tiers=[{"tier":"cycles","threshold":3}],actual_cycles=2,actual_seconds=1.0,clock=lambda:datetime(2026,7,31,tzinfo=timezone.utc),evidence_writer=writer)
   self.assertFalse(results[0].achieved);self.assertIsNone(results[0].granted_at)
   results=evaluate(declared_tiers=[{"tier":"cycles","threshold":3}],actual_cycles=3,actual_seconds=1.0,clock=lambda:datetime(2026,7,31,tzinfo=timezone.utc),evidence_writer=writer)
   self.assertTrue(results[0].achieved);self.assertIsNotNone(results[0].evidence_path)
 def test_hours_tier_requires_actual_seconds(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   writer=lambda body:paths.append(body) or f"{Path(d)/'cert'}/{len(paths)}.json"
   results=evaluate(declared_tiers=[{"tier":"hours","threshold":1,"duration_seconds":3600}],actual_cycles=10,actual_seconds=120.0,clock=lambda:datetime(2026,7,31,tzinfo=timezone.utc),evidence_writer=writer)
   self.assertFalse(results[0].achieved)
   self.assertEqual(results[0].actual_seconds,120.0)
 def test_days_tier_does_not_grant_when_unmet(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   writer=lambda body:paths.append(body) or f"{Path(d)/'cert'}/{len(paths)}.json"
   results=evaluate(declared_tiers=[{"tier":"days","threshold":1,"duration_seconds":86400}],actual_cycles=1000,actual_seconds=3600.0,clock=lambda:datetime(2026,7,31,tzinfo=timezone.utc),evidence_writer=writer)
   self.assertFalse(results[0].achieved);self.assertEqual(results[0].duration_seconds,86400)

if __name__=="__main__":unittest.main()
