import json,subprocess,sys,tempfile,threading,time,unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
 body=b"cert-1";etag='"c1"'
 def do_GET(self):
  if self.headers.get("If-None-Match")==self.etag:
   self.send_response(304);self.end_headers();return
  self.send_response(200);self.send_header("ETag",self.etag);self.end_headers();self.wfile.write(self.body)
 def log_message(self,*args):pass
class CliCertTests(unittest.TestCase):
 def setUp(self):
  self.server=HTTPServer(("127.0.0.1",0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close()
 def config(self,root,tiers):
  data={"identity":{"name":"shui","version":"1","mission":["verify"]},"values":[{"name":"truth","weight":1.0,"source":"test-evidence","calibrated_at":"2026-07-31T00:00:00+00:00"}],"sources":[{"id":"local","url":f"http://127.0.0.1:{self.server.server_port}/feed","protocol":"http"}],"goals":[{"id":"observe","description":"Observe","dependencies":[],"impacts":{"truth":1.0}}],"schedules":{"fast_seconds":1,"slow_seconds":2},"capabilities":{"enabled":["observe.http"]},"paths":{"state":"../state","actions":"../actions","audit":"../audit/events.jsonl"},"runtime":{"http_timeout_seconds":2,"capability_timeout_seconds":2,"learning_min_samples":1,"soak_cycles":3,"audit_lock_timeout_seconds":2,"audit_lock_poll_seconds":0.01},"certification":{"tiers":tiers}}
  path=root/"config"/"shui.json";path.parent.mkdir();path.write_text(json.dumps(data));return path
 def run_cli(self,args):
  return subprocess.run([sys.executable,str(ROOT/"shui.py"),*args],cwd=ROOT,capture_output=True,text=True,timeout=30)
 def test_cycles_tier_cycles_runs_emit_certificate(self):
  with tempfile.TemporaryDirectory() as d:
   config=self.config(Path(d),[{"tier":"cycles","threshold":2}])
   self.run_cli(["once","--config",config])
   self.run_cli(["once","--config",config])
   self.run_cli(["once","--config",config])
   output=self.run_cli(["cert","--config",config])
   self.assertEqual(output.returncode,0,output.stderr)
   data=json.loads(output.stdout)
   self.assertTrue(any(item["tier"]=="cycles" and item["achieved"] for item in data["tiers"]))
 def test_hours_tier_is_not_granted_under_threshold(self):
  with tempfile.TemporaryDirectory() as d:
   config=self.config(Path(d),[{"tier":"hours","threshold":1,"duration_seconds":3600}])
   self.run_cli(["once","--config",config])
   data=json.loads(self.run_cli(["cert","--config",config]).stdout)
   hours=next(item for item in data["tiers"] if item["tier"]=="hours")
   self.assertFalse(hours["achieved"])

if __name__=="__main__":unittest.main()
