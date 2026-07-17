"""飞书双向通信桥——借鉴ClaudeCode bridge模式"""
import urllib.request, json, os, logging
logger = logging.getLogger("nexus.bridge")

class FeishuBridge:
    def __init__(self):
        self.webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
        self.handlers = []

    def configure(self, webhook_url: str):
        self.webhook = webhook_url

    def send(self, text: str) -> bool:
        if not self.webhook: return False
        body = json.dumps({"msg_type":"text","content":{"text":text}}).encode()
        try:
            req = urllib.request.Request(self.webhook, body, {"Content-Type":"application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read()).get("code") == 0
        except Exception as e:
            logger.warning(f"Feishu send failed: {e}")
            return False

    def on_message(self, handler):
        self.handlers.append(handler)

    def receive(self, message: dict):
        for h in self.handlers:
            try: h(message)
            except Exception as e: logger.warning(f"Message handler failed: {e}")
