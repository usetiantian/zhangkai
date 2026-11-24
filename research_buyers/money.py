import json, os, re

OUT = os.path.dirname(os.path.abspath(__file__))
s = json.load(open(os.path.join(OUT, "code_summary.json"), encoding="utf-8"))

MONEY = re.compile(r"(?:[$€£]\s?\d[\d,\.]*\s?(?:k|K|m|M)?(?:\s?-\s?[$€£]?\s?\d[\d,\.]*\s?(?:k|K|m|M)?)?|\d[\d,]*\s?(?:k|K)\s?(?:project|retainer|month|hour|day|week)|from\s+\d)")


def pick_pages(r):
    return r.get("pages200", [])


for label, r in sorted(s.items()):
    if not r.get("alive"):
        continue
    txt = r.get("text", "")
    hits = set()
    for m in MONEY.finditer(txt):
        a = max(0, m.start() - 70)
        ctx = txt[a:m.end() + 70].replace("\n", " ")
        hits.add(ctx.strip())
    if hits:
        print("=== %s (%s)" % (label, r.get("homepage", "")[:60]))
        for h in list(hits)[:6]:
            print("   >", h[:190])
        print()
