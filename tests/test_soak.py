import tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from experiments.soak import SoakRunner

START=datetime(2026,7,31,tzinfo=timezone.utc)
class Clock:
 def __init__(self):self.now=START
 def __call__(self):
  value=self.now;self.now+=timedelta(seconds=1);return value
class SoakTests(unittest.TestCase):
 def test_report_contains_real_counts_and_growth(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);world=root/"world.db";audit=root/"audit.jsonl";world.write_bytes(b"a");audit.write_text("one\n")
   outcomes=iter(("verified","unchanged","failed","verified"))
   runner=SoakRunner(clock=Clock(),processor=lambda:next(outcomes),world_path=world,audit_path=audit,disk_path=root,world_counter=lambda:0)
   report=runner.run(cycles=4)
   self.assertEqual((report.verified,report.unchanged,report.failed),(2,1,1))
   self.assertEqual(report.attempts,4);self.assertGreaterEqual(report.duration_seconds,0)
   self.assertEqual(report.world_bytes_growth,0);self.assertEqual(report.audit_events_growth,0)
 def test_cycle_threshold_must_be_explicit_and_positive(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);runner=SoakRunner(clock=Clock(),processor=lambda:"verified",world_path=root/"w",audit_path=root/"a",disk_path=root,world_counter=lambda:0)
   with self.assertRaises(ValueError):runner.run(cycles=0)

if __name__=="__main__":unittest.main()
