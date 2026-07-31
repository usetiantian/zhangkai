import tempfile,threading,unittest
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from perception.rss.adapter import RssAdapter
from perception.sources import build_source,GitHubTags,GenericHttp

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class Handler(BaseHTTPRequestHandler):
 body=b"github";etag='"g-1"'
 def do_GET(self):
  if self.headers.get("If-None-Match")==self.etag:
   self.send_response(304);self.end_headers();return
  self.send_response(200);self.send_header("ETag",self.etag);self.end_headers();self.wfile.write(self.body)
 def log_message(self,*args):pass
class SourceRegistryTests(unittest.TestCase):
 def setUp(self):self._threads=[]
 def tearDown(self):
  for t in self._threads:t.join(timeout=2)
 def test_generic_http_factory_uses_per_source_cache(self):
  with tempfile.TemporaryDirectory() as d:
   server=HTTPServer(("127.0.0.1",0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True)
   thread.start();self._threads.append(thread)
   url=f"http://127.0.0.1:{server.server_port}/api"
   source=build_source({"id":"gh","url":url,"protocol":"http"},Path(d))
   self.assertIsInstance(source,GenericHttp)
   first=source.observe(clock=lambda:NOW)
   self.assertTrue(first.changed);self.assertEqual(source.url,url)
   server.shutdown();server.server_close()
 def test_github_protocol_alias_uses_http_with_independent_state(self):
  with tempfile.TemporaryDirectory() as d:
   server=HTTPServer(("127.0.0.1",0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True)
   thread.start();self._threads.append(thread)
   url=f"http://127.0.0.1:{server.server_port}/api"
   plain=build_source({"id":"a","url":url,"protocol":"http"},Path(d))
   alias=build_source({"id":"b","url":url,"protocol":"github_api","format":"tags"},Path(d))
   self.assertIsInstance(alias,GitHubTags);self.assertEqual(alias.url,url)
   self.assertNotEqual(plain.alias,alias.alias)
   server.shutdown();server.server_close()

if __name__=="__main__":unittest.main()
