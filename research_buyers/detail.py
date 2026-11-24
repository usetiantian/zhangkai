import json, glob, re, os, sys

want = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
recs = {}
for f in glob.glob("harvest_spec_code*.json"):
    data = json.load(open(f, encoding="utf-8"))
    if isinstance(data, dict):
        for co, pages in data.items():
            recs.setdefault(co, []).extend(pages if isinstance(pages, list) else [pages])
    else:
        for r in data:
            recs.setdefault(r["company"], []).append(r)

for co, pages in recs.items():
    if want and co not in want:
        continue
    best = None
    for p in pages:
        score = len(p.get("forms", [])) * 5 + len(p.get("emails", [])) * 3 + len(p.get("whatsapp", [])) * 3 + len(p.get("telegram", [])) * 3
        if best is None or score > best[0]:
            best = (score, p)
    if not best:
        continue
    p = best[1]
    print("=" * 100)
    print(f"{co} | {p['url']} | HTTP {p.get('status')}")
    for fo in p.get("forms", [])[:4]:
        flds = fo.get("fields", [])
        print(f"  FORM action={fo.get('action')!r} method={fo.get('method')!r} nfields={len(flds)} :: {','.join(flds[:14])}")
    if p.get("emails"):
        print(f"  EMAIL {sorted(set(p['emails']))[:6]}")
    if p.get("whatsapp"):
        print(f"  WHATSAPP {sorted(set(p['whatsapp']))[:4]}")
    if p.get("telegram"):
        print(f"  TELEGRAM {sorted(set(p['telegram']))[:4]}")
    if p.get("phones"):
        print(f"  TEL {sorted(set(p['phones']))[:4]}")
    body = p.get("text", "") or ""
    money = []
    for m in re.finditer(r"(?i)(?:[$€£]\s?[\d,]{3,}(?:[kKmM])?|\b\d+\s?(?:k|K)\s?(?:USD|EUR|GBP|dollars)?\b|from \$[\d,]+|starting (?:at|from) \$[\d,]+|minimum (?:project |budget |investment )?\$[\d,]+|as (?:low|little) as \$[\d,]+|\$[\d,]+\s?(?:per month|/month|per hour|/hour|/hr|per day|/day))", body):
        s = max(0, m.start() - 90); e = min(len(body), m.end() + 90)
        money.append(re.sub(r"\s+", " ", body[s:e]))
    seen = set()
    for mm in money[:14]:
        k = mm[:40]
        if k in seen: continue
        seen.add(k)
        print(f"  $ ~ {mm}")
