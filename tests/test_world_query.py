import tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from contracts import Claim,Conflict,Evidence,Fact
from world_model.store import WorldModel

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
BASE={"schema_version":"1","created_at":NOW}

class WorldModelQueryTests(unittest.TestCase):
 def records(self):
  evidence=Evidence(id="ev-1",observation_id="obs-1",source_uri="https://a.example/x",content_hash="sha256:a",**BASE)
  claim=Claim(id="claim-1",statement="alpha",evidence_ids=("ev-1",),**BASE)
  fact=Fact(id="fact-1",statement="alpha is true",claim_ids=("claim-1",),valid_at=NOW,**BASE)
  conflict=Conflict(id="conflict-1",record_ids=("fact-1","fact-2"),description="disagreement",**BASE)
  other=Claim(id="claim-2",statement="beta",evidence_ids=("ev-1",),**BASE)
  return evidence,claim,fact,conflict,other
 def test_query_filters_by_type_source_and_text(self):
  with tempfile.TemporaryDirectory() as d:
   model=WorldModel(Path(d)/"world.db")
   for record in self.records():model.put(record,valid_from=NOW,valid_until=NOW+timedelta(days=1))
   facts=model.query(record_type="Fact")
   self.assertEqual({item.id for item in facts},{"fact-1"})
   self.assertEqual({item.id for item in model.query(source="https://a.example/x")},{"ev-1","claim-1","fact-1","claim-2","conflict-1"})
   self.assertEqual({item.id for item in model.query(contains="alpha")},{"claim-1","fact-1"})
   self.assertEqual({item.id for item in model.query(contains="missing")},set())
 def test_explain_returns_chain_conflicts_and_validity(self):
  with tempfile.TemporaryDirectory() as d:
   model=WorldModel(Path(d)/"world.db")
   for record in self.records():model.put(record)
   explanation=model.explain("fact-1")
   self.assertEqual([record["id"] for record in explanation["chain"]],["fact-1","claim-1","ev-1"])
   self.assertIn("conflict-1",explanation["conflicts"])
   self.assertEqual(explanation["validity"],"current")
   expired=self.records()[0]
   model.put(expired,valid_from=NOW-timedelta(days=2),valid_until=NOW-timedelta(days=1))
   self.assertEqual(model.explain("ev-1")["validity"],"expired")

if __name__=="__main__":unittest.main()
