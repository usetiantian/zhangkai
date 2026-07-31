import tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from cognition.loop import ShuiLoop
from values import ValueSet, ValueWeight
from goals import GoalCandidate

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
VALUES=ValueSet((ValueWeight("learning",1.0,"owner-decision",NOW),))
CANDIDATES=(GoalCandidate("ignore","Ignore change",(),{"learning":0.0}),GoalCandidate("learn","Learn change",(),{"learning":1.0}))

class AutonomousLoopTests(unittest.TestCase):
 def test_change_drives_complete_verified_cycle(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/"world.txt"; source.write_text("new reality")
   loop=ShuiLoop(root/"state",root/"actions",clock=lambda:NOW,values=VALUES,candidates=CANDIDATES)
   result=loop.tick(source)
   self.assertEqual(result.status,"verified")
   self.assertTrue(result.receipt_verified)
   self.assertEqual(loop.world.get(result.evidence_id).id,result.evidence_id)
   self.assertTrue((root/"actions"/f"{result.observation_id}.json").exists())
 def test_unchanged_world_does_not_repeat_action(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/"world.txt"; source.write_text("same")
   first=ShuiLoop(root/"state",root/"actions",clock=lambda:NOW,values=VALUES,candidates=CANDIDATES).tick(source)
   second=ShuiLoop(root/"state",root/"actions",clock=lambda:NOW,values=VALUES,candidates=CANDIDATES).tick(source)
   self.assertEqual(first.status,"verified"); self.assertEqual(second.status,"unchanged")
 def test_changed_world_starts_new_cycle_after_restart(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/"world.txt"; source.write_text("one")
   ShuiLoop(root/"state",root/"actions",clock=lambda:NOW,values=VALUES,candidates=CANDIDATES).tick(source)
   source.write_text("two")
   result=ShuiLoop(root/"state",root/"actions",clock=lambda:NOW,values=VALUES,candidates=CANDIDATES).tick(source)
   self.assertEqual(result.status,"verified")

if __name__=="__main__":unittest.main()
