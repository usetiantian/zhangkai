import tempfile,unittest
from pathlib import Path
from audit.project import inspect_project
class ProjectAuditTests(unittest.TestCase):
 def test_audit_distinguishes_implemented_tested_and_empty_modules(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/"alpha").mkdir();(root/"beta").mkdir();(root/"tests").mkdir()
   (root/"alpha"/"engine.py").write_text("def run(): return 1")
   (root/"tests"/"test_alpha.py").write_text("from alpha.engine import run")
   report=inspect_project(root,("alpha","beta"))
   self.assertEqual(report["alpha"]["implementation_files"],1)
   self.assertEqual(report["alpha"]["test_references"],1)
   self.assertEqual(report["beta"]["implementation_files"],0)
 def test_current_project_audit_finds_unified_entry(self):
  report=inspect_project(Path.cwd(),("identity",))
  self.assertTrue(report["_project"]["unified_entry"])
if __name__=="__main__":unittest.main()
