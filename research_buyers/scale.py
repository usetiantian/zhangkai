import json, glob, re, sys

want = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
recs = {}
for f in glob.glob("harvest_spec_code*.json"):
    data = json.load(open(f, encoding="utf-8"))
    if isinstance(data, dict):
        for co, pages in data.items():
            recs.setdefault(co, []).extend(pages if isinstance(pages, list) else [pages])

PAT = re.compile(r"(?i)(?:\$[0-9][0-9,\.]*(?:\s?[kK])?(?:\s?/\s?(?:mo|month|hr|hour|day|project))?|£[0-9][0-9,\.]*k?|€[0-9][0-9,\.]*k?)")
CTX = re.compile(r"(?i).{0,110}(?:starting at|from \$|starts at|budget of|as low as|minimum|per month|per hour|per day|/mo|/month|/hour|fixed price|from £|from €|price|membership|subscription).{0,110}")

for co, pages in recs.items():
    if want and co not in want:
        continue
    hits = []
    seen = set()
    for p in pages:
        body = p.get("text", "") or ""
        for m in CTX.finditer(body):
            s = re.sub(r"\s+", " ", m.group(0))
            if not PAT.search(s):
                continue
            k = s[:60]
            if k in seen:
                continue
            seen.add(k)
            hits.append(s)
    if hits:
        print("=" * 90)
        print(co)
        for h in hits[:8]:
            print("  -", h)
