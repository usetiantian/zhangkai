import contextlib,io,json,tempfile,unittest
from pathlib import Path
from shui import main

CONFIG={
 "identity":{"name":"shui","version":"1","mission":["learn","verify"]},
 "values":[{"name":"truth","weight":1.0,"source":"owner","calibrated_at":"2026-07-31T00:00:00+00:00"}],
 "sources":[{"id":"source","url":"https://example.com"}],
 "goals":[{"id":"learn","description":"Learn change","dependencies":[],"impacts":{"truth":1.0}}],
 "schedules":{"fast_seconds":1,"slow_seconds":2},
 "capabilities":{"enabled":["observe.http"]},
 "paths":{"state":"../state","actions":"../actions","audit":"../audit/events.jsonl"},
 "runtime":{"http_timeout_seconds":1,"capability_timeout_seconds":1,"learning_min_samples":1}
}
class CliTests(unittest.TestCase):
 def config(self,root):
  path=root/"config"/"shui.json";path.parent.mkdir();path.write_text(json.dumps(CONFIG));return path
 def invoke(self,args,**kwargs):
  output=io.StringIO()
  with contextlib.redirect_stdout(output):code=main(args,**kwargs)
  return code,json.loads(output.getvalue())
 def test_check_delegates_to_project_checker(self):
  called=[];code,data=self.invoke(["check"],check_runner=lambda:called.append(True) or 0)
  self.assertEqual(code,0);self.assertEqual(called,[True]);self.assertEqual(data["status"],"ok")
 def test_once_initializes_identity_and_audit_then_status_restores_them(self):
  with tempfile.TemporaryDirectory() as d:
   config=self.config(Path(d));code,once=self.invoke(["once","--config",str(config)])
   self.assertEqual(code,0);self.assertEqual(once["status"],"completed")
   code,status=self.invoke(["status","--config",str(config)])
   self.assertEqual(status["identity"]["name"],"shui");self.assertTrue(status["audit_valid"])
   self.assertEqual(status["audit_events"],1)
   self.assertEqual(status["task_counts"],{})
   self.assertEqual(status["evolved_capabilities"],[])
 def test_run_uses_explicit_cycle_count(self):
  with tempfile.TemporaryDirectory() as d:
   config=self.config(Path(d));code,data=self.invoke(["run","--config",str(config),"--cycles","2"])
   self.assertEqual(code,0);self.assertEqual(data["cycles_completed"],2)
 def test_invalid_config_returns_failure_without_traceback(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"bad.json";path.write_text("{}")
   code,data=self.invoke(["status","--config",str(path)])
   self.assertNotEqual(code,0);self.assertEqual(data["status"],"error")

if __name__=="__main__":unittest.main()
