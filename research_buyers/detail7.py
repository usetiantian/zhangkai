import json, glob, re, sys

want = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
recs = {}
for f in glob.glob("harvest_spec_code*.json"):
    data = json.load(open(f, encoding="utf-8"))
    if isinstance(data, dict):
        for co, pages in data.items():
            recs.setdefault(co, []).extend(pages if isinstance(pages, list) else [pages])

def vis(f):
    return len([x for x in f.get("fields", []) if not x.startswith("_") and not x.startswith("wpforms[")
                and not x.startswith("form_fields[") and not x.startswith("zc_") and not x.startswith("$")
                and not x.startswith("initialReferrer") and not x.startswith("First_visited")
                and not x.startswith("Last_Visited") and not x.startswith("utm_") and not x.startswith("referrer")
                and not x.startswith("page-") and not x.startswith("captcha")])

for co, pages in recs.items():
    if want and co not in want:
        continue
    best = max(pages, key=lambda p: len(p.get("forms", [])) * 4 + len(p.get("emails", [])) * 3 + len(p.get("whatsapp", [])) * 2 + len(p.get("telegram", [])) * 2)
    forms = best.get("forms", [])
    f0 = max(forms, key=vis) if forms else None
    em = [e for e in sorted(set(best.get("emails", []))) if "@" in e and " " not in e and len(e) > 6][:3]
    wa = sorted(set(best.get("whatsapp", [])))[:1]
    tg = sorted(set(best.get("telegram", [])))[:1]
    tel = sorted(set(best.get("phones", [])))[:2]
    print(f"{co}\t{best.get('status')}\t{best.get('url')}")
    if f0:
        vf = [x for x in f0.get("fields", []) if not x.startswith("_")]
        print(f"   FORM {f0.get('method')} {f0.get('action')!r} vis={vis(f0)} {vf[:10]}")
    else:
        print("   FORM NONE")
    print(f"   EMAIL {em}\n   WA {wa} TG {tg} TEL {tel}")
