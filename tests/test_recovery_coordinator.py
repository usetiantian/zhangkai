import tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from audit.chain import AuditChain
from recovery.coordinator import RecoveryCoordinator

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class RecoveryCoordinatorTests(unittest.TestCase):
 def make(self,root,processor):
  audit=root/"audit.jsonl"
  existing=len(audit.read_text().splitlines()) if audit.exists() else 0
  counter=iter(range(existing,existing+100))
  return RecoveryCoordinator(root/"checkpoint.json",root/"heartbeat.json",AuditChain(root/"audit.jsonl"),clock=lambda:NOW,id_factory=lambda:f"event-{next(counter)}",processor=processor)
 def test_heartbeat_and_checkpoint_are_observable(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);seen=[];coordinator=self.make(root,lambda source:seen.append(source) or "verified")
   report=coordinator.run_once(("a","b"))
   self.assertEqual(seen,["a","b"]);self.assertEqual(report.completed,2)
   heartbeat=coordinator.heartbeat();self.assertEqual(heartbeat["status"],"idle")
   self.assertEqual(heartbeat["cycles_completed"],1)
   self.assertEqual(coordinator.checkpoint()["next_index"],0)
 def test_single_source_failure_is_audited_and_does_not_stop_cycle(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);seen=[]
   def process(source):
    seen.append(source)
    if source=="bad":raise RuntimeError("source failed")
    return "verified"
   report=self.make(root,process).run_once(("good","bad","later"))
   self.assertEqual(seen,["good","bad","later"]);self.assertEqual(report.failed,1)
   types=[line["event_type"] for line in self.make(root,process).audit_records()]
   self.assertIn("source.failed",types);self.assertIn("cycle.recovered",types)
 def test_process_interrupt_resumes_from_last_confirmed_source(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first_seen=[]
   def interrupt(source):
    first_seen.append(source)
    if source=="b":raise KeyboardInterrupt()
    return "verified"
   with self.assertRaises(KeyboardInterrupt):self.make(root,interrupt).run_once(("a","b","c"))
   second_seen=[];coordinator=self.make(root,lambda source:second_seen.append(source) or "verified")
   coordinator.run_once(("a","b","c"))
   self.assertEqual(first_seen,["a","b"]);self.assertEqual(second_seen,["b","c"])
   self.assertTrue(AuditChain(root/"audit.jsonl").verify())

if __name__=="__main__":unittest.main()
