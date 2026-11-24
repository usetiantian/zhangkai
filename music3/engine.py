#!/usr/bin/env python3
"""engine.py -- ComfyUI(MiniMax Music3) client + MiniMax text assistant"""
import json, os, time, urllib.error, urllib.parse, urllib.request

# bumped on every module load -- used by /api/health to prove hot-reload works
RELOAD_STAMP = time.time()

DEFAULT_SERVER = os.environ.get("COMFY_SERVER", "http://127.0.0.1:8188")

MODELS = {
    "unet":         "minimax_music3_dit_fp16.safetensors",
    "unet_lowvram": "minimax_music3_dit_int8_convrot.safetensors",
    "clip":         "minimax_music3_text_encoder_pruned_int8_convrot.safetensors",
    "vae":          "minimax_music3_dav.safetensors",
}

def build_workflow(caption, lyrics, seed, duration, cfg_scale, top_k, steps,
                   unet=None, clip=None, vae=None, prefix="music3/song",
                   fmt="mp3", quality="320k"):
    # cfg fixed at 1 -- real CFG already applied inside the text encoder
    return {
        "6":  {"class_type": "UNETLoader", "inputs": {"unet_name": unet or MODELS["unet"], "weight_dtype": "default"}},
        "3":  {"class_type": "CLIPLoader", "inputs": {"clip_name": clip or MODELS["clip"], "type": "minimax", "device": "default"}},
        "7":  {"class_type": "VAELoader", "inputs": {"vae_name": vae or MODELS["vae"]}},
        "13": {"class_type": "MiniMaxMusic3TextEncode",
               "inputs": {"clip": ["3", 0], "caption": caption, "lyrics": lyrics, "seed": seed,
                          "max_duration": duration, "cfg_scale": cfg_scale, "top_k": top_k}},
        "10": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["13", 0]}},
        "15": {"class_type": "EmptyMiniMaxMusic3LatentAudio",
               "inputs": {"seconds": ["13", 1], "batch_size": 1}},
        "9":  {"class_type": "KSampler",
               "inputs": {"model": ["6", 0], "positive": ["13", 0], "negative": ["10", 0],
                          "latent_image": ["15", 0], "seed": seed, "steps": steps, "cfg": 1.0,
                          "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "42": {"class_type": "VAEDecodeAudioTiled",
               "inputs": {"samples": ["9", 0], "vae": ["7", 0], "tile_size": 1536, "overlap": 64}},
        "35": {"class_type": "SaveAudioAdvanced",
               "inputs": {"audio": ["42", 0], "filename_prefix": prefix,
                          "format": fmt, "format.quality": quality}},
    }


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, server=DEFAULT_SERVER):
        self.server = server.rstrip("/")

    def _req(self, url, payload=None, timeout=90, raw=False):
        if payload is None:
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if raw else json.loads(r.read().decode("utf-8"))

    def alive(self):
        try:
            self._req(self.server + "/system_stats", timeout=5)
            return True
        except Exception:
            return False

    def queue_info(self):
        try:
            return self._req(self.server + "/queue", timeout=10)
        except Exception:
            return {}

    def submit(self, workflow):
        resp = self._req(self.server + "/prompt",
                         {"prompt": workflow, "client_id": "music3-web"}, timeout=60)
        if "error" in resp:
            raise ComfyError("ComfyUI rejected workflow: " + json.dumps(resp["error"], ensure_ascii=False)[:600])
        pid = resp.get("prompt_id")
        if not pid:
            raise ComfyError("no prompt_id: " + json.dumps(resp, ensure_ascii=False)[:400])
        return pid

    def history(self, prompt_id):
        try:
            return self._req(self.server + "/history/" + prompt_id, timeout=20).get(prompt_id, {})
        except Exception:
            return {}

    def audio_meta(self, prompt_id):
        entry = self.history(prompt_id)
        for out in entry.get("outputs", {}).values():
            if out.get("audio"):
                a = out["audio"][0]
                return a["filename"], a.get("subfolder", ""), a.get("type", "output")
        return None

    def fetch_audio(self, filename, subfolder="", type_="output"):
        q = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
        return self._req(self.server + "/view?" + q, timeout=300, raw=True)

    def run(self, workflow, poll=2, timeout=2400):
        pid = self.submit(workflow)
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(poll)
            entry = self.history(pid)
            if not entry:
                continue
            st = entry.get("status", {})
            if st.get("status_str") == "error":
                raise ComfyError("generation failed: " + json.dumps(st, ensure_ascii=False)[:800])
            for out in entry.get("outputs", {}).values():
                if out.get("audio"):
                    a = out["audio"][0]
                    return (self.fetch_audio(a["filename"], a.get("subfolder", ""), a.get("type", "output")),
                            a["filename"])
            if st.get("completed"):
                raise ComfyError("done but no audio output, check ComfyUI log")
        raise ComfyError("timeout %ds" % timeout)


# ---------------- MiniMax text assistant ----------------

# (label, url_template, model, needs_group_id)
# Tries international first, then the China platform, then the legacy v2 route.
MM_ENDPOINTS = [
    ("国际站 chat/completions", "https://api.minimax.io/v1/chat/completions", "MiniMax-M3.1-Flash", False),
    ("国内站 chat/completions", "https://api.minimaxi.com/v1/chat/completions", "MiniMax-M3.1-Flash", False),
    ("国际站 M3", "https://api.minimax.io/v1/chat/completions", "MiniMax-M3", False),
    ("国内站 M3", "https://api.minimaxi.com/v1/chat/completions", "MiniMax-M3", False),
    ("国际站 chatcompletion_v2", "https://api.minimax.io/v1/text/chatcompletion_v2", "MiniMax-Text-01", False),
    ("国内站 chatcompletion_v2", "https://api.minimaxi.com/v1/text/chatcompletion_v2", "MiniMax-Text-01", True),
]

FENCE = chr(96) * 3


class TextError(RuntimeError):
    pass


class MiniMaxText:
    """Tries each endpoint in turn. The key lives only in memory, never on disk."""

    def __init__(self, api_key, group_id=""):
        self.key = self._clean(api_key)
        self.group_id = (group_id or "").strip()

    @staticmethod
    def _clean(key):
        """Tolerate keys pasted with whitespace, backticks, quotes or a Bearer prefix."""
        k = (key or "").strip()
        k = k.strip("`").strip()
        k = k.strip("'").strip('"').strip()
        if k.lower().startswith("bearer "):
            k = k[7:].strip()
        return k

    def _url(self, template, needs_gid):
        if needs_gid and self.group_id:
            return template + "?GroupId=" + urllib.parse.quote(self.group_id)
        return template

    def list_models(self, timeout=25):
        """Ask the platform which models this key may use. Returns (platform, ids)."""
        errors = []
        for label, base in (("国际站", "https://api.minimax.io"), ("国内站", "https://api.minimaxi.com")):
            try:
                req = urllib.request.Request(base + "/v1/models",
                                             headers={"Authorization": "Bearer " + self.key})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
                ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
                if ids:
                    return label, ids
                errors.append("%s: 返回为空" % label)
            except urllib.error.HTTPError as e:
                errors.append("%s: HTTP %d" % (label, e.code))
            except Exception as e:
                errors.append("%s: %s" % (label, str(e)[:80]))
        return None, errors

    def _once(self, url, model, system, user, timeout):
        body = {"model": model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}]}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read()[:300].decode("utf-8", "ignore")
            try:
                j = json.loads(raw)
                msg = j.get("error", {}).get("message") or j.get("base_resp", {}).get("status_msg") or raw
            except Exception:
                msg = raw
            raise RuntimeError("HTTP %d %s" % (e.code, msg))
        br = data.get("base_resp", {})
        if br.get("status_code", 0) not in (0,):
            raise RuntimeError(br.get("status_msg") or json.dumps(br, ensure_ascii=False))
        err = data.get("error")
        if err:
            raise RuntimeError(err.get("message") or json.dumps(err, ensure_ascii=False))
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError("unexpected reply: " + json.dumps(data, ensure_ascii=False)[:200])

    def chat(self, system, user, timeout=120):
        if not self.key:
            raise TextError("没有填 API key")
        errors = []
        combos = list(MM_ENDPOINTS)
        # If the static model list misses, ask the platform what this key can use.
        platform, models_or_errors = self.list_models(timeout=20)
        if platform:
            for mid in models_or_errors:
                for label, base in (("国际站 chat/completions", "https://api.minimax.io/v1/chat/completions"),
                                    ("国内站 chat/completions", "https://api.minimaxi.com/v1/chat/completions")):
                    if (label, mid, False) not in combos:
                        combos.append((label, base, mid, False))
        for label, template, model, needs_gid in combos:
            url = self._url(template, needs_gid)
            try:
                return self._once(url, model, system, user, timeout)
            except Exception as e:
                errors.append("%s [%s]: %s" % (label, model, str(e)[:180]))
        raise TextError("所有端点都失败：\n" + "\n".join(errors))

    def probe(self, timeout=25):
        """Diagnose a key: which platform, which models, which combo actually works.

        Returns (winner, attempts, models_report).
        """
        if not self.key:
            return None, [{"endpoint": "-", "model": "-", "error": "没有填 API key"}], None

        attempts = []
        winner = None

        # 1) ask the platform which models this key can see
        platform, models_or_errors = self.list_models(timeout)
        if platform:
            models_report = "可用模型（%s）：%s" % (platform, ", ".join(models_or_errors))
            attempts.append({"endpoint": platform + " /v1/models",
                             "model": ", ".join(models_or_errors), "error": None})
        else:
            models_report = "列模型失败：%s" % "; ".join(models_or_errors)
            attempts.append({"endpoint": "/v1/models", "model": "-", "error": models_report})

        # 2) try the static combo list
        combos = list(MM_ENDPOINTS)
        # 3) plus every model the platform just told us about
        if platform:
            for mid in models_or_errors:
                for label, base in (("国际站 chat/completions", "https://api.minimax.io/v1/chat/completions"),
                                    ("国内站 chat/completions", "https://api.minimaxi.com/v1/chat/completions")):
                    if (label, mid, False) not in combos:
                        combos.append((label, base, mid, False))

        for label, template, model, needs_gid in combos:
            url = self._url(template, needs_gid)
            try:
                self._once(url, model, "reply with the single word: ok", "ping", timeout)
                attempts.append({"endpoint": label, "model": model, "error": None})
                if winner is None:
                    winner = "%s / %s" % (label, model)
            except Exception as e:
                attempts.append({"endpoint": label, "model": model, "error": str(e)[:200]})
        return winner, attempts, models_report


def parse_json_loose(text):
    """Pull a JSON object out of an LLM reply, tolerating code fences and chatter."""
    t = (text or "").strip()
    if FENCE in t:
        for p in t.split(FENCE):
            p = p.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") and p.endswith("}"):
                t = p
                break
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        t = t[i:j + 1]
    return json.loads(t)


ARRANGE_SYS = (
    "You are a senior music producer and arranger. You turn a one-sentence idea into a "
    "precise ACOUSTIC BRIEF for a text-to-music model (MiniMax Music3). "
    "The model does not understand commands or song titles -- it understands production "
    "descriptors. Write the brief in CHINESE as one dense paragraph, covering: "
    "genre/style, BPM, key and mode, tempo feel, overall mood, song structure "
    "(Intro/Verse/Chorus/Bridge with time ranges), instrument roles, vocal type, "
    "mix and production texture, and the use case (e.g. short-video BGM, loop, vlog). "
    "Be concrete and evocative. No preamble, no bullet points, no song names, no artist names."
)

LYRICS_SYS = (
    "You are a professional lyricist writing CHINESE lyrics for a song. "
    "Output ONLY the lyrics, using section tags like [Intro] [Verse] [Chorus] [Bridge]. "
    "Every line ends with a newline. Keep it colloquial and visual, avoid narration, "
    "and make the chorus short, repeatable and memorable. No commentary."
)


def ai_arrange(text, api_key, group_id=""):
    """One sentence -> detailed arrangement brief (Chinese)."""
    out = MiniMaxText(api_key, group_id).chat(
        ARRANGE_SYS,
        "根据下面这句话，写出详细编曲说明：\n\n" + text)
    return out.strip()


def ai_lyrics(theme, api_key, style="", group_id=""):
    """Theme -> Chinese lyrics with section tags."""
    extra = ("\n曲风参考：" + style) if style else ""
    out = MiniMaxText(api_key, group_id).chat(
        LYRICS_SYS,
        "主题：" + theme + extra)
    return out.strip()
