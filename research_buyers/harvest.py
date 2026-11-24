import json, re, ssl, os, sys, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

OUT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(OUT, "raw")
os.makedirs(RAW, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = r.read()
            enc = None
            try:
                enc = r.headers.get_content_charset()
            except Exception:
                pass
            if not enc:
                enc = "utf-8"
            try:
                html = data.decode(enc, errors="replace")
            except Exception:
                html = data.decode("utf-8", errors="replace")
            return {"url": r.geturl(), "status": r.status, "html": html}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {"url": url, "status": e.code, "html": body, "err": "HTTP %s" % e.code}
    except Exception as e:
        return {"url": url, "status": 0, "html": "", "err": "%s: %s" % (type(e).__name__, e)}

TAG_RE = re.compile(r"<[^>]+>")
def strip_tags(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", h)
    h = TAG_RE.sub(" ", h)
    h = re.sub(r"&nbsp;?", " ", h)
    h = re.sub(r"&amp;", "&", h)
    h = re.sub(r"&#\d+;", " ", h)
    return re.sub(r"[ \t\r\f\v]+", " ", h).strip()

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,12}")
BAD_MAIL = ("example.com", "your@email", "domain.com", "sentry.io", "w3.org", "email.com",
            "yourdomain", "sentry.wixpress", "placeholder", "@2x", "emailaddress",
            "name@your", "test@", "sample.com", "company.com", "yourcompany")
TEL_RE = re.compile(r"tel:([+0-9()\- ]{7,25})", re.I)
WA_RE = re.compile(r"(?:wa\.me|api\.whatsapp\.com|web\.whatsapp\.com)[^\s\"'<>]*", re.I)
TG_RE = re.compile(r"(?:t\.me|telegram\.me)/[A-Za-z0-9_\-]+", re.I)

def norm_email(e):
    e = e.strip().strip(".").lower()
    if e in ("",) or len(e) < 6:
        return None
    for b in BAD_MAIL:
        if b in e:
            return None
    dom = e.split("@")[-1]
    if dom.endswith(".png") or dom.endswith(".jpg") or dom.endswith(".jpeg") or dom.endswith(".gif") or dom.endswith(".webp") or dom.endswith(".svg"):
        return None
    return e

def extract_forms(html, base_url):
    forms = []
    for m in re.finditer(r"(?is)<form\b([^>]*)>(.*?)</form>", html):
        attrs_raw = m.group(1)
        inner = m.group(2)
        attrs = dict((k.lower(), v) for k, v in re.findall(r'([\w:\-]+)\s*=\s*"([^"]*)"', attrs_raw))
        attrs.update({k.lower(): v for k, v in re.findall(r"([\w:\-]+)\s*=\s*'([^']*)'", attrs_raw)})
        action = attrs.get("action", "")
        method = (attrs.get("method", "GET") or "GET").upper()
        if action:
            action_abs = urllib.parse.urljoin(base_url, action)
        else:
            action_abs = base_url
        fields = []
        for fm in re.finditer(r"(?is)<(input|textarea|select)\b([^>]*)>", inner):
            tag = fm.group(1)
            a = fm.group(2)
            nm = re.search(r'name\s*=\s*["\']([^"\']+)["\']', a)
            ty = re.search(r'type\s*=\s*["\']([^"\']+)["\']', a)
            req = ("required" in a.lower())
            if nm:
                fields.append({"name": nm.group(1),
                               "type": (ty.group(1) if ty else tag).lower(),
                               "required": req})
        # netlify / formspree / web3forms detection
        providers = []
        blob = (m.group(0) or "")[:20000] + html[:60000]
        for prov, pat in (("netlify", r"data-netlify"), ("formspree", r"formspree\.io"),
                          ("web3forms", r"web3forms\.com"), ("getform", r"getform\.io"),
                          ("google", r"docs\.google\.com/forms"), ("hubspot", r"hubspot"),
                          ("wpforms", r"wpforms"), ("contactout", r"contactout"),
                          ("basin", r"usebasin\.com"), ("formstack", r"formstack"),
                          ("recaptcha", r"grecaptcha|recaptcha"), ("turnstile", r"challenges\.cloudflare\.com")):
            if re.search(pat, blob, re.I):
                providers.append(prov)
        # honeypot field
        honeypot = ""
        for fm in re.finditer(r"(?is)<input\b([^>]*)>", inner):
            a = fm.group(1)
            if re.search(r"(?i)bot|honeypot|_gotcha|website|company_url|leave.*blank", a) and 'type="hidden"' in a.lower():
                honeypot = re.search(r'name\s*=\s*["\']([^"\']+)["\']', a).group(1) if re.search(r'name\s*=\s*["\']([^"\']+)["\']', a) else "?"
        forms.append({
            "action": action_abs, "action_raw": action or "(none=page itself)",
            "method": method,
            "n_fields": len(fields),
            "fields": [f["name"] for f in fields][:22],
            "required": [f["name"] for f in fields if f["required"]][:12],
            "providers": sorted(set(providers)),
            "honeypot": honeypot,
        })
    return forms

def analyze(url, label):
    res = fetch(url)
    html = res.get("html", "")
    d = {
        "label": label, "url": url, "final_url": res.get("url"),
        "status": res.get("status"), "err": res.get("err"),
        "title": (re.search(r"(?is)<title[^>]*>(.*?)</title>", html).group(1).strip()[:160] if re.search(r"(?is)<title[^>]*>(.*?)</title>", html) else ""),
        "len": len(html),
    }
    if res.get("status") and res.get("status") >= 400:
        d["dead"] = True
        return d
    d["forms"] = extract_forms(html, res.get("url") or url)
    txt = strip_tags(html)
    d["emails"] = sorted(set(filter(None, (norm_email(e) for e in EMAIL_RE.findall(txt)))))
    # also mailto in raw
    d["mailtos"] = sorted(set(m.lower() for m in re.findall(r"mailto:([^\"'\s?]+)", html, re.I)))[:8]
    d["emails"] = sorted(set(d["emails"] + [m for m in d["mailtos"] if norm_email(m)]))
    d["tel"] = sorted(set(re.sub(r"[^\d+]", "", t) for t in TEL_RE.findall(html) if len(re.sub(r"\D", "", t)) >= 7))[:6]
    d["whatsapp"] = sorted(set(WA_RE.findall(html)))[:3]
    d["telegram"] = sorted(set(TG_RE.findall(html)))[:3]
    d["text"] = txt[:4200]
    # external submit endpoints
    eps = set()
    for pat in (r"action\s*=\s*[\"']([^\"']+)[\"']", r"fetch\([\"']([^\"']+)[\"']",
                r"[\"'](/api/[^\"']{3,60})[\"']", r"[\"'](https://api\.[^\"']{3,60})[\"']"):
        for m in re.findall(pat, html):
            if any(k in m.lower() for k in ("form", "submit", "contact", "api", "send")):
                eps.add(m[:120])
    d["endpoints"] = sorted(eps)[:12]
    return d

def job(args):
    label, urls = args
    out = []
    for u in urls:
        r = analyze(u, label)
        out.append(r)
        print("%-28s %-3s %s f=%d m=%d e=%d %s" % (
            label[:28], r.get("status"), u[:78], len(r.get("forms", [])),
            len(r.get("emails", [])), len(r.get("telegram", []) + r.get("whatsapp", [])),
            (r.get("title") or "")[:40]))
        sys.stdout.flush()
    return out

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    tasks = []
    for label, urls in spec.items():
        tasks.append((label, urls))
    results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for label, rows in zip([t[0] for t in tasks], ex.map(job, tasks)):
            results[label] = rows
    base = os.path.splitext(os.path.basename(sys.argv[1]))[0]
    json.dump(results, open(os.path.join(OUT, "harvest_%s.json" % base), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("SAVED harvest_%s.json" % base)
