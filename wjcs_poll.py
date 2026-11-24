# -*- coding: utf-8 -*-
import json, sys, time, urllib.request
API = "http://127.0.0.1:8188"
pid = open(r"C:\Users\87999\claude-workspace\wjcs_prompt_id.txt").read().strip()
def get(p):
    return json.loads(urllib.request.urlopen(API+p, timeout=60).read().decode("utf-8"))
h = get("/history/"+pid)
if pid in h:
    hh=h[pid]; st=hh.get("status",{})
    print("STATUS:", st.get("status_str"), "completed:", st.get("completed"))
    if st.get("status_str")=="error":
        print(json.dumps(st, ensure_ascii=False)[:4000])
    else:
        print(json.dumps(hh.get("outputs",{}), ensure_ascii=False)[:3000])
else:
    q=get("/queue"); r=q.get("queue_running",[]); p=q.get("queue_pending",[])
    print("running:",len(r),"pending:",len(p))
    for x in r:
        try: print("  node:", list(x[2].values())[0].get("class_type"))
        except Exception: pass
