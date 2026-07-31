import subprocess,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from audit.chain import AuditChain
from audit.lock import InterProcessLock

ROOT=Path(__file__).resolve().parents[1]
class AuditConcurrencyTests(unittest.TestCase):
 def test_independent_processes_append_without_loss(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl";worker=ROOT/"tests"/"audit_worker.py"
   processes=[subprocess.Popen([sys.executable,str(worker),str(path),f"p{i}","5"],cwd=ROOT) for i in range(4)]
   codes=[process.wait(timeout=30) for process in processes]
   self.assertEqual(codes,[0,0,0,0])
   chain=AuditChain(path,lock_timeout_seconds=2,lock_poll_seconds=.01)
   self.assertTrue(chain.verify());self.assertEqual(len(path.read_text().splitlines()),20)
 def test_os_releases_lock_after_process_exit(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl";lock_path=path.with_suffix(".jsonl.lock")
   code=("import os,sys;from pathlib import Path;from audit.lock import InterProcessLock;"
         "lock=InterProcessLock(Path(sys.argv[1]),timeout_seconds=2,poll_seconds=.01);"
         "ctx=lock.hold();ctx.__enter__();os._exit(0)")
   result=subprocess.run([sys.executable,"-c",code,str(lock_path)],cwd=ROOT)
   self.assertEqual(result.returncode,0)
   chain=AuditChain(path,lock_timeout_seconds=2,lock_poll_seconds=.01)
   chain.append("after-crash",datetime.now(timezone.utc),"recovered",None,"ok",{})
   self.assertTrue(chain.verify())

if __name__=="__main__":unittest.main()
