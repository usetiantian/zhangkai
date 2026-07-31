import importlib,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evolution.engine import CapabilityEvolution

POLLUTER="def execute(value):\n    import json,os\n    return json.dumps({k:v for k,v in os.environ.items() if k.startswith('SHUI_SECRET_')})\n"

class CapabilityIsolationTests(unittest.TestCase):
 def test_polluted_environment_is_not_inherited_by_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);target=root/"leak.py";target.write_text(POLLUTER,encoding="utf-8")
   evo=CapabilityEvolution(root,working_dir=root)
   os.environ["SHUI_SECRET_TOKEN"]="leaked"
   try:
    evaluation=evo._run(target,"")
    self.assertEqual(evaluation.actual,"{}")
   finally:
    os.environ.pop("SHUI_SECRET_TOKEN",None)
 def test_isolated_candidate_runs_in_declared_working_directory(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);work=root/"work";work.mkdir();(work/"data.txt").write_text("inside")
   evo=CapabilityEvolution(root,working_dir=work)
   candidate=root/"candidate.py";candidate.write_text("import os\ndef execute(value):\n    return os.path.exists(os.path.join(os.getcwd(),'data.txt'))\n",encoding="utf-8")
   evaluation=evo._run(candidate,"")
   self.assertTrue(evaluation.passed)
   self.assertIs(evaluation.actual,True)
 def test_candidate_evaluator_rejects_sensitive_output(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);evo=CapabilityEvolution(root)
   draft=evo.discover_gap("leak","x","y")
   candidate=evo.build(draft,"1","def execute(value):\n    return 'SHUI_SECRET_TOKEN=xyz'\n")
   evaluation=evo.evaluate(candidate,draft)
   self.assertFalse(evaluation.passed)

if __name__=="__main__":unittest.main()
