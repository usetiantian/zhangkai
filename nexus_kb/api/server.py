"""
HTTP API Server — 纯 Python，零外部依赖

启动: python -m nexus_kb.api.server --port 8765

端点:
  GET  /health                    → 健康检查
  GET  /status                    → 知识库状态
  POST /search   {"q":"..."}      → 搜索
  POST /ingest   {"path":"..."}   → 摄入文件
  POST /ingest_text {"text":"...","source":"..."} → 摄入文本
  POST /rescan                    → 重新扫描数据湖
  GET  /graph/:id                 → 图谱邻居
  POST /detect_communities        → 社区检测
"""

import json, os, logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("nexus_kb.api")

# 全局引用，由 serve() 注入
_kb = None


def serve(kb, host: str = "127.0.0.1", port: int = 8765):
    global _kb
    _kb = kb
    server = HTTPServer((host, port), _Handler)
    logger.info(f"API server: http://{host}:{port}")
    print(f"Nexus KB API: http://{host}:{port}")
    print(f"  GET  /health")
    print(f"  GET  /status")
    print(f"  POST /search  {{\"q\": \"...\"}}")
    print(f"  POST /ingest  {{\"path\": \"...\"}}")
    print(f"  POST /rescan")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        logger.debug(f"API: {args[0]}")

    def _send(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        if self.path == "/health":
            return self._send({"status": "ok"})
        if self.path == "/status":
            return self._send(_kb.status())
        if self.path.startswith("/graph/"):
            nid = self.path.split("/")[-1]
            return self._send({"neighbors": _kb.graph_neighbors(nid)})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        if self.path == "/search":
            q = body.get("q", "")
            k = body.get("k", 10)
            return self._send({"results": _kb.search(q, k), "query": q})
        if self.path == "/ingest":
            path = body.get("path", "")
            if not path or not os.path.exists(path):
                return self._send({"error": "file not found"}, 400)
            return self._send(_kb.ingest_file(path))
        if self.path == "/ingest_text":
            text = body.get("text", "")
            source = body.get("source", "api_input")
            _kb.ingest_text(text, source)
            return self._send({"status": "ok", "source": source, "chars": len(text)})
        if self.path == "/rescan":
            results = _kb.rescan()
            return self._send({"count": len(results), "results": results})
        if self.path == "/detect_communities":
            return self._send({"communities": _kb.detect_communities()})
        if self.path == "/web_search":
            q = body.get("q", "")
            k = body.get("k", 5)
            ingest = body.get("ingest", False)
            if ingest:
                r = _kb.web_search_and_ingest(q, k)
            else:
                r = _kb.web_search(q, k)
            return self._send({"results": r, "query": q})
        if self.path == "/web_fetch":
            return self._send(_kb.web_fetch(body.get("url", "")))
        self._send({"error": "not found"}, 404)
