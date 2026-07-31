import json,sqlite3,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from evolution import CapabilityEvolution
from execution import FileExecutor
from experiments.fault_matrix import FaultMatrix,FaultScenario
from learning import LearningStore

class FaultMatrixTests(unittest.TestCase):
 def test_eight_fault_classes_are_contained_and_recovered(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);scenarios=[]
   scenarios.append(FaultScenario("http_timeout",lambda:(_ for _ in ()).throw(TimeoutError()),TimeoutError,lambda:True))
   scenarios.append(FaultScenario("http_error",lambda:(_ for _ in ()).throw(ConnectionError()),ConnectionError,lambda:True))
   db=root/"locked.db";store=LearningStore(db);lock=sqlite3.connect(db);lock.execute("BEGIN EXCLUSIVE")
   scenarios.append(FaultScenario("sqlite_lock",lambda:store.predict("p","s","success"),sqlite3.OperationalError,lambda:(lock.rollback() or lock.close() or True)))
   corrupt=root/"checkpoint.json";corrupt.write_text("{")
   scenarios.append(FaultScenario("corrupt_state",lambda:json.loads(corrupt.read_text()),json.JSONDecodeError,lambda:(corrupt.write_text('{}')>=0)))
   scenarios.append(FaultScenario("execution_timeout",lambda:(_ for _ in ()).throw(subprocess.TimeoutExpired("capability",1)),subprocess.TimeoutExpired,lambda:True))
   target=root/"target.txt";target.write_text("before")
   def disk_failure():
    with patch("execution.runtime.os.replace",side_effect=OSError("disk failure")):
     FileExecutor(root).write(target,b"after")
   scenarios.append(FaultScenario("disk_write",disk_failure,OSError,lambda:target.read_text()=="before"))
   evo=CapabilityEvolution(root/"evo");draft=evo.discover_gap("upper","a","A")
   candidate=evo.build(draft,"1","def execute(value):\n return value.lower()\n")
   scenarios.append(FaultScenario("capability_failure",lambda:evo.promote(candidate,evo.evaluate(candidate,draft)),ValueError,lambda:not evo.is_registered("upper")))
   subprocess.run(["git","init","-q",str(root/"repo")],check=True)
   def git_failure():
    subprocess.run(
     ["git","ls-remote","invalid://unreachable/repository"],
     check=True,capture_output=True,text=True,
    )
   def git_recovery():
    return subprocess.run(
     ["git","-C",str(root/"repo"),"status","--porcelain"],
     capture_output=True,
    ).returncode==0
   scenarios.append(
    FaultScenario(
     "git_network",git_failure,subprocess.CalledProcessError,git_recovery,
    )
   )
   report=FaultMatrix().run(scenarios)
   self.assertEqual(len(report),8);self.assertTrue(all(item.contained and item.recovered for item in report))
 def test_unexpected_success_is_reported_not_hidden(self):
  report=FaultMatrix().run([FaultScenario("bad_test",lambda:None,ValueError,lambda:True)])
  self.assertFalse(report[0].contained);self.assertEqual(report[0].status,"unexpected_success")

if __name__=="__main__":unittest.main()
