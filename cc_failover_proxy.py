# -*- coding: utf-8 -*-
"""CC 故障转移代理：智谱(主) -> MiniMax(辅)
- 平时所有请求发给智谱 glm-5.3
- 遇到 429/5xx/401/网络错误 -> 自动改发 MiniMax-M3
- 只监听 127.0.0.1，密钥不出本机
- 日志: %USERPROFILE%/.claude/cc_proxy.log
"""
import json, os, re, sys, time, threading
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CC_PROXY_PORT", "8790"))
LOG = os.path.join(os.path.expanduser("~"), ".claude", "cc_proxy.log")
def _load_keys():
    """密钥不写进代码：优先环境变量，其次 ~/.claude/cc_keys.json"""
    keys = {}
    p = os.path.join(os.path.expanduser("~"), ".claude", "cc_keys.json")
    try:
        with open(p, encoding="utf-8") as f:
            keys = json.load(f)
    except Exception:
        pass
    return keys


_KEYS = _load_keys()

PRIMARY = {
    "name": "zhipu",
    "base": "https://open.bigmodel.cn/api/anthropic",
    "token": os.environ.get("ZHIPU_API_KEY") or _KEYS.get("ZHIPU_TOKEN", ""),
}
FALLBACK = {
    "name": "minimax",
    "base": "https://api.minimaxi.com/anthropic",
    "token": os.environ.get("ANTHROPIC_AUTH_TOKEN") or _KEYS.get("MINIMAX_TOKEN", ""),
}
# 测试模式: 主路由指向不通的地址，验证故障转移
if os.environ.get("CC_PROXY_TEST") == "1":
    PRIMARY["base"] = "https://127.0.0.1:9"

FALLBACK_CODES = {401, 403, 429, 500, 502, 503, 504, 529}
STATS = {"total": 0, "primary": 0, "fallback": 0, "both_failed": 0}
_lock = threading.Lock()

def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 5 * 1024 * 1024:
            os.remove(LOG)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass

def norm_primary_model(m):
    m = re.sub(r"\[.*?\]$", "", m or "")
    if "flash" in m or "haiku" in m:
        return "glm-5.3-flash"
    if m.startswith("glm"):
        return m
    return "glm-5.3"  # claude-* 一律映射到 glm-5.3

def wants_minimax(raw):
    """用户在 Claude Code 里 /model MiniMax-M3 -> 直接走 MiniMax（手动切换）"""
    try:
        m = json.loads(raw).get("model", "")
    except Exception:
        return False
    return "minimax" in re.sub(r"\[.*?\]$", "", m).lower()

def rewrite_body(raw, target):
    """按目标厂商改写请求体里的 model 字段"""
    try:
        d = json.loads(raw)
    except Exception:
        return raw
    m = d.get("model", "")
    if target is PRIMARY:
        d["model"] = norm_primary_model(m)
    else:
        d["model"] = "MiniMax-M3"
    return json.dumps(d, ensure_ascii=False).encode("utf-8")

def call_target(target, method, path, headers, body):
    url = target["base"] + path
    h = {k: v for k, v in headers.items()
         if k.lower() not in ("host", "authorization", "x-api-key",
                              "accept-encoding", "content-length", "connection")}
    h["Authorization"] = "Bearer " + target["token"]
    h["Accept-Encoding"] = "identity"
    return requests.request(method, url, headers=h, data=body,
                            timeout=(15, 600), stream=True)

class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # 用关闭连接代替 chunked，流式照常

    def log_message(self, *a):
        pass

    def _serve(self):
        if self.path == "/__health":
            with _lock:
                s = dict(STATS)
            body = json.dumps({"ok": True, **s}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        hdrs = {k: v for k, v in self.headers.items()}
        t0 = time.time()

        with _lock:
            STATS["total"] += 1

        resp, used = None, None
        err = ""
        manual = wants_minimax(raw)
        if manual:
            err = "manual /model -> minimax"
        if not manual:
            try:
                resp = call_target(PRIMARY, self.command, self.path, hdrs,
                                   rewrite_body(raw, PRIMARY))
                used = PRIMARY
                if resp.status_code in FALLBACK_CODES:
                    err = "primary %s" % resp.status_code
                    resp.close()
                    resp = None
            except Exception as e:
                err = "primary net: %s" % type(e).__name__

        if resp is None:  # 主路由失败 -> 切 MiniMax
            try:
                resp = call_target(FALLBACK, self.command, self.path, hdrs,
                                   rewrite_body(raw, FALLBACK))
                used = FALLBACK
            except Exception as e:
                err += " | fallback net: %s" % type(e).__name__

        if resp is None:
            with _lock:
                STATS["both_failed"] += 1
            body = json.dumps({"type": "error", "error": {
                "type": "api_error",
                "message": "CC 代理: 主辅模型都连不上。%s" % err}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            log("FAIL  %s %s (%s)" % (self.command, self.path, err))
            return

        with _lock:
            STATS["primary" if used is PRIMARY else "fallback"] += 1

        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() in ("content-length", "content-encoding",
                             "transfer-encoding", "connection"):
                continue
            self.send_header(k, v)
        self.end_headers()
        nbytes = 0
        try:
            for chunk in resp.iter_content(chunk_size=4096):
                if chunk:
                    self.wfile.write(chunk)
                    nbytes += len(chunk)
        except Exception:
            pass
        finally:
            resp.close()
        model = ""
        try:
            model = json.loads(raw).get("model", "")
        except Exception:
            pass
        log("%-4s %-8s %s model=%s bytes=%d %.1fs%s"
            % (resp.status_code, used["name"], self.path, model,
               nbytes, time.time() - t0,
               "  <- " + err if err else ""))

    do_GET = do_POST = do_PUT = do_DELETE = _serve

if __name__ == "__main__":
    try:  # 已有实例在跑就直接退出，避免端口冲突
        import socket
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1)
        s.close()
        sys.exit(0)
    except Exception:
        pass
    log("=== 代理启动 pid=%d port=%d ===" % (os.getpid(), PORT))
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Proxy)
    srv.daemon_threads = True
    srv.serve_forever()
