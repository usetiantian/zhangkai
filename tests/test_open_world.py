import tempfile,threading,unittest
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from perception.web.adapter import HttpAdapter
from attention.engine import SourceCandidate,SourceSelector,AttentionWeights,attention_score
from cognition.scheduler import Scheduler
from perception.web.monitor import StabilityMonitor

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class Handler(BaseHTTPRequestHandler):
 body=b"version-one";etag='"v1"';requests=[]
 def do_GET(self):
  type(self).requests.append(dict(self.headers))
  if self.headers.get("If-None-Match")==type(self).etag:self.send_response(304);self.end_headers();return
  self.send_response(200);self.send_header("ETag",type(self).etag);self.end_headers();self.wfile.write(type(self).body)
 def log_message(self,*args):pass

class OpenWorldTests(unittest.TestCase):
 def setUp(self):
  Handler.body=b"version-one";Handler.etag='"v1"';Handler.requests=[]
  self.server=HTTPServer(("127.0.0.1",0),Handler);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
  self.url=f"http://127.0.0.1:{self.server.server_port}/feed"
 def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close()
 def test_source_selection_uses_supplied_evidence(self):
  candidates=[SourceCandidate("a",.8,.9,.7,.6),SourceCandidate("b",.9,.4,.9,.8)]
  weights=AttentionWeights(.4,.2,.2,.2)
  ranking=SourceSelector(weights).rank(candidates)
  self.assertEqual(ranking[0].id,"b")
  self.assertGreater(attention_score(.9,.4,.9,.8,weights),attention_score(.8,.9,.7,.6,weights))
 def test_http_cache_and_conditional_request(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=HttpAdapter(Path(d),clock=lambda:NOW)
   first=adapter.observe(self.url);second=adapter.observe(self.url)
   self.assertTrue(first.changed);self.assertFalse(second.changed)
   self.assertEqual(second.content,b"version-one")
   self.assertEqual(Handler.requests[-1]["If-None-Match"],'"v1"')
 def test_changed_remote_content_creates_new_observation(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=HttpAdapter(Path(d),clock=lambda:NOW);first=adapter.observe(self.url)
   Handler.body=b"version-two";Handler.etag='"v2"'
   second=adapter.observe(self.url)
   self.assertTrue(second.changed);self.assertNotEqual(first.content_hash,second.content_hash)
 def test_attention_score_uses_external_weights(self):
  weights=AttentionWeights(.25,.25,.25,.25)
  self.assertEqual(attention_score(.8,.4,.2,.6,weights),.5)
 def test_continuous_monitor_reports_real_counts(self):
  with tempfile.TemporaryDirectory() as d:
   report=StabilityMonitor(HttpAdapter(Path(d),clock=lambda:NOW)).run(self.url,cycles=6)
   self.assertEqual(report.attempts,6);self.assertEqual(report.failures,0)
   self.assertEqual(report.changed,1);self.assertEqual(report.unchanged,5)
 def test_fast_and_slow_schedules_are_caller_defined(self):
  scheduler=Scheduler({"fast":timedelta(seconds=2),"slow":timedelta(seconds=5)})
  self.assertEqual(scheduler.due(NOW),["fast","slow"]);scheduler.mark("fast",NOW);scheduler.mark("slow",NOW)
  self.assertEqual(scheduler.due(NOW+timedelta(seconds=2)),["fast"])
  self.assertEqual(scheduler.due(NOW+timedelta(seconds=5)),["fast","slow"])

if __name__=="__main__":unittest.main()
