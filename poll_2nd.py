# -*- coding: utf-8 -*-
import json, urllib.request, time, sys
API="http://127.0.0.1:8188"
ids=open(r"C:\Users\87999\claude-workspace\wjcs_2nd_ids.txt").read().split()
def get(p): return json.loads(urllib.request.urlopen(API+p,timeout=60).read().decode())
for pid in ids:
    h=get("/history/"+pid)
    if pid in h:
        st=h[pid].get("status",{})
        print(pid[:8], st.get("status_str"), "completed:", st.get("completed"))
        if st.get("status_str")=="error":
            print(json.dumps(st,ensure_ascii=False)[:2500])
    else:
        print(pid[:8], "RUNNING")
q=get("/queue"); print("queue running:",len(q.get("queue_running",[])),"pending:",len(q.get("queue_pending",[])))
