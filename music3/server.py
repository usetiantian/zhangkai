#!/usr/bin/env python3
"""server.py -- web UI for music3.

Binds 127.0.0.1 only (this machine). The LAN/mobile variant lives in
server_lan.py, which is a separate opt-in script.
"""
import json, os, socket, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer as _ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine

HERE = os.path.dirname(os.path.abspath(__file__))

_SRC_MTIME = {}


def _maybe_reload():
    """Reload engine.py when it changes on disk, so AI-logic edits apply without a restart."""
    p = os.path.join(HERE, "engine.py")
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return
    if _SRC_MTIME.get("engine") is None:
        _SRC_MTIME["engine"] = mt
    elif mt > _SRC_MTIME["engine"]:
        _SRC_MTIME["engine"] = mt
        try:
            import importlib
            importlib.reload(engine)
            print("[music3] engine.py 已热重载", flush=True)
        except Exception as e:
            print("[music3] 热重载失败: %s" % e)
STATIC = os.path.join(HERE, "static")
DEFAULT_PORT = int(os.environ.get("MUSIC3_PORT", "8899"))
COMFY = engine.DEFAULT_SERVER

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8", ".json": "application/json",
        ".svg": "image/svg+xml", ".ico": "image/x-icon", ".png": "image/png"}

JOBS = {}
JOB_LOCK = threading.Lock()
AUDIO_CACHE = {}
CACHE_ORDER = []
CACHE_MAX = 60


def new_job(jid, prompt_id, seed, **meta):
    with JOB_LOCK:
        JOBS[jid] = dict(id=jid, prompt_id=prompt_id, seed=seed, state="queued",
                         created=time.time(), error=None, filename=None, **meta)


def get_job(jid):
    with JOB_LOCK:
        return JOBS.get(jid)


def cache_audio(key, data):
    with JOB_LOCK:
        AUDIO_CACHE[key] = data
        CACHE_ORDER.append(key)
        while len(CACHE_ORDER) > CACHE_MAX:
            AUDIO_CACHE.pop(CACHE_ORDER.pop(0), None)


def cached(key):
    with JOB_LOCK:
        return AUDIO_CACHE.get(key)


def make_seeds(count, seed):
    """count distinct seeds; seed=None -> random base."""
    import random
    base = seed if seed is not None else random.randint(0, 2 ** 31)
    return [(base + i * 7919) % (2 ** 32) for i in range(count)]


CFG_LADDER = [1.4, 1.6, 1.8, 2.0]


class ThreadingHTTPServer(_ThreadingHTTPServer):
    # On Windows the default SO_REUSEADDR lets a second process bind a port that
    # is already taken, which silently splits traffic between two servers.
    # We want a hard failure instead, so the caller can pick another port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    server_version = "music3/1.0"

    def log_message(self, fmt, *args):
        pass

    # ---------- helpers ----------
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _static(self, name):
        path = os.path.normpath(os.path.join(STATIC, name.lstrip("/")))
        if not path.startswith(STATIC) or not os.path.isfile(path):
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            data = f.read()
        self._send(200, data, MIME.get(ext, "application/octet-stream"))

    # ---------- routes ----------
    def do_GET(self):
        _maybe_reload()
        p = urllib.parse.urlparse(self.path)
        path = p.path
        q = urllib.parse.parse_qs(p.query)

        if path == "/" or path == "/index.html":
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path == "/api/health":
            c = engine.ComfyClient(COMFY)
            return self._json({"ok": True, "app": "music3", "comfy": c.alive(),
                               "comfy_server": COMFY,
                               "queue": c.queue_info(),
                               "engine_stamp": round(getattr(engine, "RELOAD_STAMP", 0), 3)})
        if path == "/api/jobs":
            with JOB_LOCK:
                return self._json({"jobs": list(JOBS.values())})
        if path == "/api/doctor":
            import doctor
            return self._json(doctor.report(COMFY))
        if path.startswith("/api/status/"):
            return self._status(path.rsplit("/", 1)[-1])
        if path.startswith("/api/audio/"):
            return self._audio(path.rsplit("/", 1)[-1], dl=(q.get("dl", ["0"])[0] == "1"))
        self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        _maybe_reload()
        p = urllib.parse.urlparse(self.path)
        body = self._body()
        if p.path == "/api/ai/arrange":
            return self._ai_arrange(body)
        if p.path == "/api/ai/lyrics":
            return self._ai_lyrics(body)
        if p.path == "/api/ai/test":
            return self._ai_test(body)
        if p.path == "/api/generate":
            return self._generate(body)
        self._send(404, "not found", "text/plain; charset=utf-8")

    # ---------- handlers ----------
    def _ai_arrange(self, body):
        key = body.get("api_key", "")
        gid = body.get("group_id", "")
        text = (body.get("text") or "").strip()
        if not text:
            return self._json({"error": "描述是空的"}, 400)
        try:
            caption = engine.ai_arrange(text, key, gid)
        except engine.TextError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            return self._json({"error": str(e)}, 500)
        return self._json({"caption": caption})

    def _ai_lyrics(self, body):
        key = body.get("api_key", "")
        gid = body.get("group_id", "")
        theme = (body.get("theme") or "").strip()
        if not theme:
            return self._json({"error": "主题是空的"}, 400)
        try:
            lyrics = engine.ai_lyrics(theme, key, body.get("style", ""), gid)
        except engine.TextError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            return self._json({"error": str(e)}, 500)
        return self._json({"lyrics": lyrics})

    def _ai_test(self, body):
        """Probe every endpoint/model combo and report which one works."""
        winner, attempts, models_report = engine.MiniMaxText(
            body.get("api_key", ""), body.get("group_id", "")).probe()
        return self._json({"ok": bool(winner), "winner": winner,
                           "attempts": attempts, "models": models_report})

    def _generate(self, body):
        caption = (body.get("caption") or "").strip()
        if not caption:
            return self._json({"error": "empty caption"}, 400)
        lyrics = body.get("lyrics") or ""
        duration = float(body.get("duration", 60))
        steps = int(body.get("steps", 20))
        cfg = float(body.get("cfg", 1.7))
        top_k = int(body.get("top_k", 50))
        count = max(1, min(8, int(body.get("count", 1))))
        variation = body.get("variation", "seed")
        seed = body.get("seed")
        seed = int(seed) if seed not in (None, "", "null") else None
        fmt = body.get("format", "mp3")
        quality = body.get("quality", "320k")
        unet = engine.MODELS["unet_lowvram"] if body.get("lowvram") else engine.MODELS["unet"]

        # variation=seed -> different seed each (different take)
        # variation=cfg  -> same seed, CFG ladder (same melody, different adherence)
        if variation == "cfg":
            import random
            base = seed if seed is not None else random.randint(0, 2 ** 31)
            seeds = [base] * count
            cfgs = CFG_LADDER[:count]
        else:
            seeds = make_seeds(count, seed)
            cfgs = [cfg] * count
        c = engine.ComfyClient(COMFY)
        jobs = []
        for i in range(count):
            wf = engine.build_workflow(
                caption=caption, lyrics=lyrics, seed=seeds[i],
                duration=duration, cfg_scale=cfgs[i], top_k=top_k, steps=steps,
                unet=unet, prefix="music3/web_%s" % seeds[i],
                fmt=fmt, quality=quality)
            try:
                pid = c.submit(wf)
            except Exception as e:
                return self._json({"error": "submit failed: %s" % e}, 500)
            jid = "%s_%d" % (pid[:12], i)
            new_job(jid, pid, seeds[i], caption=caption, lyrics=bool(lyrics),
                    duration=duration, cfg=cfgs[i], steps=steps)
            jobs.append(dict(id=jid, prompt_id=pid, seed=seeds[i], cfg=cfgs[i]))
        return self._json({"jobs": jobs})

    def _status(self, jid):
        job = get_job(jid)
        if not job:
            return self._json({"error": "no such job"}, 404)
        c = engine.ComfyClient(COMFY)
        entry = c.history(job["prompt_id"])
        st = entry.get("status", {})
        state = job["state"]
        if st.get("status_str") == "error":
            state = "error"
            job["error"] = json.dumps(st, ensure_ascii=False)[:600]
        else:
            meta = c.audio_meta(job["prompt_id"])
            if meta:
                state = "ready"
                job["filename"] = meta[0]
            elif st.get("completed"):
                state = "error"
                job["error"] = job["error"] or "completed with no audio"
            elif state == "queued":
                state = "running"
        job["state"] = state
        return self._json({"id": jid, "state": state, "seed": job["seed"], "cfg": job["cfg"],
                           "filename": job.get("filename"), "error": job.get("error"),
                           "audio_url": "/api/audio/" + jid if state == "ready" else None})

    def _audio(self, jid, dl=False):
        job = get_job(jid)
        if not job:
            return self._send(404, "no such job", "text/plain; charset=utf-8")
        data = cached(jid)
        if data is None:
            c = engine.ComfyClient(COMFY)
            meta = c.audio_meta(job["prompt_id"])
            if not meta:
                return self._send(404, "not ready", "text/plain; charset=utf-8")
            try:
                data = c.fetch_audio(*meta)
            except Exception as e:
                return self._send(500, str(e), "text/plain; charset=utf-8")
            cache_audio(jid, data)
        fn = job.get("filename") or (jid + ".mp3")
        disp = fn.split("/")[-1]
        extra = {"Content-Disposition": ('attachment; filename="%s"' % disp) if dl
                 else 'inline; filename="%s"' % disp}
        ctype = "audio/mpeg" if disp.lower().endswith(".mp3") else "application/octet-stream"
        self._send(200, data, ctype, extra)


def main():
    import argparse
    global COMFY
    ap = argparse.ArgumentParser(description="music3 web UI (loopback only)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--comfy", default=COMFY, help="ComfyUI server URL")
    args = ap.parse_args()

    COMFY = args.comfy

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("=" * 56)
    print("  music3 web UI")
    print("  ComfyUI : %s" % COMFY)
    print("  地址    : http://127.0.0.1:%d  (仅本机)" % args.port)
    print("  想让手机访问: python server_lan.py")
    print("=" * 56)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
