import tempfile,threading,unittest
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from cognition.runtime import LearningRuntime
from goals import GoalCandidate
from values import ValueSet,ValueWeight

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class Handler(BaseHTTPRequestHandler):
 body=b"first";etag='"1"'
 def do_GET(self):
  self.send_response(200);self.send_header("ETag",self.etag);self.end_headers();self.wfile.write(self.body)
 def log_message(self,*args):pass
class RuntimeLearningTests(unittest.TestCase):
 def setUp(self):
  Handler.body=b"first";Handler.etag='"1"';self.server=HTTPServer(("127.0.0.1",0),Handler)
  self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start();self.url=f"http://127.0.0.1:{self.server.server_port}/x"
 def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close()
 def runtime(self,root):
  values=ValueSet((ValueWeight("truth",1.0,"owner",NOW),))
  goals=(GoalCandidate("a","A",(),{"truth":1.0}),GoalCandidate("b","B",(),{"truth":0.1}))
  return LearningRuntime(root/"state",root/"actions",root/"audit.jsonl",root/"cache",clock=lambda:NOW,values=values,candidates=goals,http_timeout_seconds=1,min_samples=2)
 def test_prediction_is_persisted_before_verified_result(self):
  with tempfile.TemporaryDirectory() as d:
   runtime=self.runtime(Path(d));result=runtime.tick(self.url)
   outcome=runtime.learning.get(result.prediction_id)
   self.assertEqual(outcome.strategy,"a");self.assertEqual(outcome.actual,"success")
 def test_verified_experience_changes_later_goal_selection(self):
  with tempfile.TemporaryDirectory() as d:
   runtime=self.runtime(Path(d))
   for index in range(2):
    runtime.learning.predict(f"prior-{index}","b","success")
    runtime.learning.observe(f"prior-{index}","success")
   result=runtime.tick(self.url)
   self.assertEqual(result.goal_id,"b")

if __name__=="__main__":unittest.main()
