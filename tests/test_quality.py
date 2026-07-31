import tempfile,unittest
from pathlib import Path
from audit.quality import scan
class QualityTests(unittest.TestCase):
 def test_scan_finds_compressed_and_long_lines(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"bad.py";path.write_text("def f():\n    x=1; y=2\n    return '"+"x"*110+"'\n")
   issues=scan(Path(d))
   self.assertEqual({i.kind for i in issues},{"multiple_statements","long_line"})
 def test_clean_code_has_no_issues(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/"ok.py").write_text("def f() -> int:\n    return 1\n")
   self.assertEqual(scan(Path(d)),[])
if __name__=="__main__":unittest.main()
