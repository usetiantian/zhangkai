import subprocess,tempfile,unittest
from pathlib import Path
from perception.system_metrics.adapter import SystemMetricsAdapter
from perception.github.git_adapter import GitAdapter

class ExternalSystemTests(unittest.TestCase):
 def test_local_system_snapshot_contains_observed_values(self):
  snapshot=SystemMetricsAdapter().observe(Path.cwd())
  self.assertGreater(snapshot.disk_total,0);self.assertGreaterEqual(snapshot.disk_free,0)
  self.assertTrue(snapshot.platform);self.assertTrue(snapshot.python_version)
 def test_git_adapter_reads_real_repository_state(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);subprocess.run(["git","init","-q",str(root)],check=True)
   (root/"x.txt").write_text("x")
   state=GitAdapter(root).observe()
   self.assertTrue(state.is_repository);self.assertIn("x.txt",state.untracked)
 def test_non_repository_is_reported_not_faked(self):
  with tempfile.TemporaryDirectory() as d:
   state=GitAdapter(Path(d)).observe()
   self.assertFalse(state.is_repository);self.assertIsNone(state.branch)

if __name__=="__main__":unittest.main()
