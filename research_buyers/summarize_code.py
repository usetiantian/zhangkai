import json, os, glob, re

OUT = os.path.dirname(os.path.abspath(__file__))
rows = {}
for p in sorted(glob.glob(os.path.join(OUT, "harvest_spec_code*.json"))):
    d = json.load(open(p, encoding="utf-8"))
    for label, pages in d.items():
        r = rows.setdefault(label, {"label": label, "pages": []})
        r["pages"].extend(pages)

def best_page(r):
    """pick page with most signal: forms > emails"""
    best = None; bs = -1
    for pg in r["pages"]:
        s = len(pg.get("forms", [])) * 5 + len(pg.get("emails", [])) * 3 + \
            (2 if pg.get("status") == 200 else 0) + len(pg.get("whatsapp", [])) * 3 + len(pg.get("telegram", [])) * 3
        if s > bs:
            bs = s; best = pg
    return best

summary = {}
for label, r in rows.items():
    alive = [p for p in r["pages"] if p.get("status") == 200]
    if not alive:
        summary[label] = {"label": label, "alive": False, "pages": r["pages"]}
        continue
    forms_all = []
    for pg in alive:
        for f in pg.get("forms", []):
            f2 = dict(f); f2["page"] = pg["url"]; forms_all.append(f2)
    emails = sorted(set(e for pg in alive for e in pg.get("emails", [])))
    wa = sorted(set(w for pg in alive for w in pg.get("whatsapp", [])))
    tg = sorted(set(t for pg in alive for t in pg.get("telegram", [])))
    tels = sorted(set(t for pg in alive for t in pg.get("tel", [])))
    summary[label] = {
        "label": label, "alive": True,
        "homepage": r["pages"][0]["url"],
        "pages200": [p["url"] for p in alive],
        "title": (alive[0].get("title") or "")[:120],
        "forms": forms_all,
        "n_forms": len(forms_all),
        "emails": emails,
        "whatsapp": wa, "telegram": tg, "tel": tels,
        "text": alive[0].get("text", "")[:6000],
    }

json.dump(summary, open(os.path.join(OUT, "code_summary.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

for label, s in sorted(summary.items(), key=lambda x: -(x[1].get("n_forms", 0) + len(x[1].get("emails", [])))):
    if not s["alive"]:
        print("== %-22s DEAD" % label); continue
    print("== %-22s forms=%d emails=%d wa=%d tg=%d tel=%d" % (
        label, s["n_forms"], len(s["emails"]), len(s["whatsapp"]), len(s["telegram"]), len(s["tel"])))
    for f in s["forms"][:3]:
        print("     [%s] %s %s fields=%s req=%s prov=%s hp=%s" % (
            f["method"], (f["action"] or "")[:95], "", f["fields"][:8], f["required"][:6], f["providers"], f["honeypot"]))
    if s["emails"]: print("     mail:", s["emails"][:4])
    if s["whatsapp"]: print("     wa:", s["whatsapp"][:2])
    if s["telegram"]: print("     tg:", s["telegram"][:2])
    if s["tel"]: print("     tel:", s["tel"][:3])
print("\nTOTAL alive:", sum(1 for s in summary.values() if s["alive"]))
