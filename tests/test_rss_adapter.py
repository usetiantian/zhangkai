import tempfile,threading,unittest,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from perception.rss.adapter import RssAdapter

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
FEED1=b"""<?xml version='1.0' encoding='utf-8'?>
<rss version='2.0'><channel><title>releases</title>
<item><title>v1</title><link>https://example.com/1</link><pubDate>2026-07-01</pubDate></item>
<item><title>v2</title><link>https://example.com/2</link><pubDate>2026-07-02</pubDate></item>
</channel></rss>"""
FEED2=b"""<?xml version='1.0' encoding='utf-8'?>
<rss version='2.0'><channel><title>releases</title>
<item><title>v3</title><link>https://example.com/3</link><pubDate>2026-07-10</pubDate></item>
</channel></rss>"""

class Handler(BaseHTTPRequestHandler):
 feed=FEED1;etag='"rss-1"';path="/feed"
 def do_GET(self):
  if self.path!=self.path:
   self.send_response(400);self.end_headers();return
  if self.headers.get("If-None-Match")==self.etag:
   self.send_response(304);self.end_headers();return
  self.send_response(200);self.send_header("ETag",self.etag);self.send_header("Content-Type","application/rss+xml");self.end_headers();self.wfile.write(self.feed)
 def log_message(self,*args):pass
class RssAdapterTests(unittest.TestCase):
 def setUp(self):
  self.server=HTTPServer(("127.0.0.1",0),Handler);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
  self.url=f"http://127.0.0.1:{self.server.server_port}/feed"
 def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close()
 def test_first_observation_captures_etag_and_items(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=RssAdapter(Path(d)/"cache",clock=lambda:NOW)
   observation=adapter.observe("local",self.url)
   self.assertEqual(len(observation.items),2);self.assertEqual(observation.etag,'"rss-1"')
   self.assertEqual(observation.items[0].title,"v1")
 def test_unchanged_feed_does_not_duplicate(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=RssAdapter(Path(d)/"cache",clock=lambda:NOW)
   first=adapter.observe("local",self.url);second=adapter.observe("local",self.url)
   self.assertTrue(first.changed);self.assertFalse(second.changed)
 def test_new_item_creates_new_observation(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=RssAdapter(Path(d)/"cache",clock=lambda:NOW)
   adapter.observe("local",self.url)
   Handler.feed=FEED2;Handler.etag='"rss-2"'
   observation=adapter.observe("local",self.url)
   self.assertTrue(observation.changed);self.assertEqual([item.title for item in observation.items],["v3"])

if __name__=="__main__":unittest.main()
