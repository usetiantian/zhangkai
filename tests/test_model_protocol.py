import json,tempfile,threading,unittest
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.request import urlopen as real_urlopen
from models.protocol import ModelRequest,ModelResponse,ModelError
from models.builtin import NullModelAdapter,CommandModelAdapter,OpenAICompatibleAdapter

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  length=int(self.headers.get("Content-Length","0"))
  raw=self.rfile.read(length)
  Handler.captured["body"]=json.loads(raw);Handler.captured["header"]=dict(self.headers.items())
  self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
  self.wfile.write(json.dumps({"choices":[{"message":{"content":"pong"}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}).encode())
 def log_message(self,*args):pass

class ModelProtocolTests(unittest.TestCase):
 def setUp(self):
  Handler.captured={};self.captured=Handler.captured
  self.server=HTTPServer(("127.0.0.1",0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.url=f"http://127.0.0.1:{self.server.server_port}/v1"
 def tearDown(self):self.server.shutdown();self.server.server_close()
 def test_request_and_response_are_immutable(self):
  request=ModelRequest(prompt="hello",system="test",max_tokens=10)
  with self.assertRaises((AttributeError,TypeError)):request.prompt="changed"
  response=ModelResponse(text="ok",prompt_tokens=1,completion_tokens=2,model_id="m")
  self.assertEqual(response.text,"ok")
 def test_null_adapter_never_fails(self):
  response=NullModelAdapter().complete(ModelRequest(prompt="x",system="y",max_tokens=8))
  self.assertEqual(response.text,"")
 def test_command_adapter_runs_local_program(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"echo.py"
   path.write_text("import sys\nprint(sys.stdin.read().strip().upper())\n",encoding="utf-8")
   adapter=CommandModelAdapter(["python",str(path)])
   response=adapter.complete(ModelRequest(prompt="hello",system="hi",max_tokens=8),input_text="ping")
   self.assertEqual(response.text.strip(),"PING")
 def test_openai_compatible_adapter_sends_expected_request(self):
  adapter=OpenAICompatibleAdapter(self.url,model_id="probe")
  response=adapter.complete(ModelRequest(prompt="hello",system="secret-system",max_tokens=4),token="abc")
  self.assertEqual(response.text,"pong")
  self.assertEqual(Handler.captured["body"]["messages"][-1]["content"],"hello")
  self.assertEqual(Handler.captured["body"]["model"],"probe")
  self.assertEqual(Handler.captured["header"]["Authorization"],"Bearer abc")
 def test_openai_adapter_fails_when_token_missing(self):
  adapter=OpenAICompatibleAdapter(self.url,model_id="m")
  with self.assertRaises(ModelError):adapter.complete(ModelRequest(prompt="x",system="y",max_tokens=1))

if __name__=="__main__":unittest.main()
