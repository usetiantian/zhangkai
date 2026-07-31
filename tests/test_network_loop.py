import tempfile,threading,unittest
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from audit.chain import AuditChain
from cognition.network_loop import NetworkLoop
from goals import GoalCandidate
from values import ValueSet,ValueWeight

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class Handler(BaseHTTPRequestHandler):
 body=b"network-change";etag='"n1"'
 def do_GET(self):
  if self.headers.get("If-None-Match")==self.etag:
   self.send_response(304);self.end_headers();return
  self.send_response(200);self.send_header("ETag",self.etag);self.end_headers();self.wfile.write(self.body)
 def log_message(self,*args):pass

class NetworkLoopTests(unittest.TestCase):
 def setUp(self):
  self.server=HTTPServer(("127.0.0.1",0),Handler);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
  self.url=f"http://127.0.0.1:{self.server.server_port}/feed"
 def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close()
 def make_loop(self,root):
  values=ValueSet((ValueWeight("learning",1.0,"owner",NOW),))
  goals=(GoalCandidate("learn","Learn network change",(),{"learning":1.0}),)
  return NetworkLoop(root/"state",root/"actions",root/"audit.jsonl",root/"cache",clock=lambda:NOW,values=values,candidates=goals,http_timeout_seconds=1)
 def test_http_change_forms_complete_verified_audit_chain(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);loop=self.make_loop(root);result=loop.tick(self.url)
   self.assertEqual(result.status,"verified")
   types=[line["event_type"] for line in loop.audit_records()]
   self.assertEqual(types,["observation.created","evidence.persisted","plan.selected","prediction.recorded","action.receipted","verification.completed"])
   self.assertTrue(AuditChain(root/"audit.jsonl").verify())
   self.assertEqual(len(loop.world.all()),3)
 def test_http_304_does_not_repeat_action_or_audit(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);loop=self.make_loop(root);first=loop.tick(self.url)
   count=len(loop.audit_records());second=loop.tick(self.url)
   self.assertEqual(first.status,"verified");self.assertEqual(second.status,"unchanged")
   self.assertEqual(len(loop.audit_records()),count)

if __name__=="__main__":unittest.main()
