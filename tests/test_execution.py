import tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from execution.runtime import TaskStore, FileExecutor, verify_receipt

NOW=datetime(2026,7,31,tzinfo=timezone.utc)

class ExecutionTests(unittest.TestCase):
 def test_lease_is_exclusive_and_survives_restart(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"tasks.db"; store=TaskStore(db); store.create("task-1","key-1")
   self.assertTrue(store.acquire("task-1","worker-a",NOW+timedelta(minutes=1),NOW))
   self.assertFalse(TaskStore(db).acquire("task-1","worker-b",NOW+timedelta(minutes=1),NOW))
 def test_idempotency_key_returns_existing_task(self):
  with tempfile.TemporaryDirectory() as d:
   store=TaskStore(Path(d)/"tasks.db")
   self.assertEqual(store.create("task-1","same"),"task-1")
   self.assertEqual(store.create("task-2","same"),"task-1")
 def test_executor_writes_verifies_and_rolls_back(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); target=root/"result.txt"; target.write_text("before")
   receipt=FileExecutor(root).write(target,b"after")
   self.assertTrue(verify_receipt(receipt)); self.assertEqual(target.read_bytes(),b"after")
   FileExecutor(root).rollback(receipt); self.assertEqual(target.read_bytes(),b"before")
 def test_executor_cannot_escape_declared_root(self):
  with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
   with self.assertRaises(ValueError): FileExecutor(Path(d)).write(Path(outside)/"x",b"x")
 def test_failed_task_can_be_reacquired_after_lease_expiry(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"tasks.db"; store=TaskStore(db); store.create("t","k")
   store.acquire("t","a",NOW,NOW-timedelta(seconds=1))
   self.assertTrue(TaskStore(db).acquire("t","b",NOW+timedelta(seconds=1),NOW))

if __name__=="__main__": unittest.main()
