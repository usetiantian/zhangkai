import json, glob, re, sys

SEL = """worthwebscraping webscrapingagency websbyspider leadscampaign scrapingpros extracthelp
datascraperin webdatainsights productdatascrape webdatascraping datagrass justmetrically nannostomus
3idatascraping datagators potentpages hirinfotech btobconnection crawlnow rookresearch pinobyte
sammdata scrapemasters2 webdataextractionservices datadiveedge scrapecrew
agentproai companyautomation thinkaiworks evrenai guacagents qodeonlabs itzea myriah roidigital
helpwithautomation smbstudio fuselio rot8studio ariusautomation trinitycloud zapsstudio jakealberio
tezeract smbaiteam growthnexus getautomated fyclabs
itechnosol nextenvision decipherzone bantechsolutions codalyst mindrind aptluma prosabbir whitelabelpartner
kwiqwork way2outsource canopussoft murmusoft devsstation e2msolutions ukad ivemind brilio stacksmesh
whitelabelaiagency jordanaldton sevencollab bytestechnolab quickway keyntech
algora opire bountyhub fixpool taskbounty
custommt modelfront jobdatafeeds jobspipe xtmai onestopasia""".split()

recs = {}
for f in glob.glob("harvest_spec_code*.json"):
    data = json.load(open(f, encoding="utf-8"))
    if isinstance(data, dict):
        for co, pages in data.items():
            recs.setdefault(co, []).extend(pages if isinstance(pages, list) else [pages])

SCALE = re.compile(r"(?i).{0,90}(?:starting at \$|from \$|starts at \$|budget of \$|as low as \$|minimum|per month|per hour|per day|\$[\d,]+/mo|£[\d,]+|€[\d,]+|membership|from £).{0,90}")

for co in SEL:
    pages = recs.get(co, [])
    if not pages:
        print(f"{co}\tNOPAGE"); continue
    # best page = most forms+emails
    best = max(pages, key=lambda p: len(p.get("forms", [])) * 4 + len(p.get("emails", [])) * 3 + len(p.get("whatsapp", [])) * 2 + len(p.get("telegram", [])) * 2)
    forms = best.get("forms", [])
    f0 = forms[0] if forms else None
    # pick form that has most visible (non-hid) fields
    def visible(f):
        return len([x for x in f.get("fields", []) if not x.startswith("_") and not x.startswith("wpforms[") and not x.startswith("form_fields[")])
    f0 = max(forms, key=visible) if forms else None
    em = sorted(set(best.get("emails", [])))
    em = [e for e in em if "@" in e and " " not in e and len(e) > 6][:3]
    wa = sorted(set(best.get("whatsapp", [])))[:1]
    tg = sorted(set(best.get("telegram", [])))[:1]
    tel = sorted(set(best.get("phones", [])))[:2]
    sc = []
    for p in pages:
        for m in SCALE.finditer(p.get("text", "") or ""):
            s = re.sub(r"\s+", " ", m.group(0))
            if re.search(r"\d", s) and s[:50] not in [x[:50] for x in sc]:
                sc.append(s)
    print("=" * 110)
    print(f"CO\t{co}")
    print(f"URL\t{best.get('url')}\tHTTP {best.get('status')}")
    if f0:
        vf = [x for x in f0.get("fields", []) if not x.startswith("_") and not x.startswith("wpforms[") and not x.startswith("form_fields[")]
        print(f"FORM\tmethod={f0.get('method')} action={f0.get('action')!r} visible_fields({visible(f0)})={vf[:12]}")
    else:
        print("FORM\tNONE")
    print(f"EMAIL\t{em}")
    print(f"WA\t{wa}\nTG\t{tg}\nTEL\t{tel}")
    for s in sc[:3]:
        print(f"SCALE\t{s}")
