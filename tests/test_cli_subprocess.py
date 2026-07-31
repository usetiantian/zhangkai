import json,subprocess,sys,tempfile,threading,time,unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
 body=b"e2e";etag='"e2e-1"'
 def do_GET(self):
  if self.headers.get("If-None-Match")==self.etag:
   self.send_response(304);self.end_headers();return
  self.send_response(200);self.send_header("ETag",self.etag);self.end_headers();self.wfile.write(self.body)
 def log_message(self,*args):pass
class CliSubprocessTests(unittest.TestCase):
 def setUp(self):
  self.server=HTTPServer(("127.0.0.1",0),Handler);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
 def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close()
 def config(self,root):
  data={"identity":{"name":"shui","version":"1","mission":["verify"]},"values":[{"name":"truth","weight":1.0,"source":"test-evidence","calibrated_at":"2026-07-31T00:00:00+00:00"}],"sources":[{"id":"local","url":f"http://127.0.0.1:{self.server.server_port}/feed","protocol":"http"}],"goals":[{"id":"observe","description":"Observe","dependencies":[],"impacts":{"truth":1.0}}],"schedules":{"fast_seconds":1,"slow_seconds":2},"capabilities":{"enabled":["observe.http","write.verified-report"]},"paths":{"state":"../state","actions":"../actions","audit":"../audit/events.jsonl"},"runtime":{"http_timeout_seconds":2,"capability_timeout_seconds":2,"learning_min_samples":1,"soak_cycles":2,"audit_lock_timeout_seconds":2,"audit_lock_poll_seconds":0.01},
  "certification":{"tiers":[{"tier":"cycles","threshold":6,"duration_seconds":0}]}}
  path=root/"config"/"shui.json";path.parent.mkdir();path.write_text(json.dumps(data));return path
 def command(self,*args):
  return subprocess.run([sys.executable,str(ROOT/"shui.py"),*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=30)
 def test_once_run_and_status_have_real_process_side_effects(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);config=self.config(root)
   once=self.command("once","--config",config);self.assertEqual(once.returncode,0,once.stderr)
   run=self.command("run","--config",config,"--cycles","2");self.assertEqual(run.returncode,0,run.stderr)
   status=self.command("status","--config",config);data=json.loads(status.stdout)
   self.assertEqual(data["world_records"],3);self.assertTrue(data["audit_valid"])
   self.assertTrue((root/"state"/"checkpoint.json").exists());self.assertTrue((root/"state"/"heartbeat.json").exists())
 def test_bad_config_returns_json_and_nonzero_exit(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"bad.json";path.write_text("{}")
   result=self.command("status","--config",path)
   self.assertNotEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout)["status"],"error")
 def test_terminated_run_restarts_from_durable_state(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);config=self.config(root)
   process=subprocess.Popen([sys.executable,str(ROOT/"shui.py"),"run","--config",str(config)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True)
   heartbeat=root/"state"/"heartbeat.json";deadline=time.time()+15
   while time.time()<deadline:
    if heartbeat.exists() and json.loads(heartbeat.read_text()).get("status")=="idle":break
    time.sleep(.05)
   self.assertTrue(heartbeat.exists());process.terminate();process.wait(timeout=10)
   restarted=self.command("once","--config",config);self.assertEqual(restarted.returncode,0,restarted.stderr)
   status=json.loads(self.command("status","--config",config).stdout)
   self.assertTrue(status["audit_valid"]);self.assertEqual(status["world_records"],3)

if __name__=="__main__":unittest.main()
