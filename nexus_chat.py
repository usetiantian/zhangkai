# -*- coding: utf-8 -*-
"""nexus_chat.py — Stage 28: 一行 CLI 问 Nexus."""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path("C:/Users/87999/.nexus")))


def _imp(spec):
    """Import 'module:attr'; return attr or Exception."""
    try:
        m, _, a = spec.partition(":")
        o = __import__(m, fromlist=[a or "_"])
        return getattr(o, a) if a else o
    except Exception as e:
        return e


def _err(d, k, e):
    d.setdefault("errors", {})[k] = f"{type(e).__name__}: {e}"


def classify(q):
    if any(k in q for k in ("改什么", "改进", "优化", "修复", "诊断")):
        return "optimize"
    if any(k in q for k in ("能学", "学吗", "试试", "推荐")):
        return "explore"
    return "self"


def handle_self(d, show):
    sa = _imp("nexus_agent.self_awareness:get_self_awareness")
    if isinstance(sa, Exception): return _err(d, "import_sa", sa)
    try:
        inst = sa(); d["parts"]["express_state"] = inst.express_state()
        if show:
            s = inst.sync()
            d["parts"]["snapshot"] = {"unity": round(s.unity_score, 3),
                                      "curiosity": round(s.curiosity, 3),
                                      "domains": len(s.known_domains)}
    except Exception as e: _err(d, "express_state", e)
    up = _imp("nexus_agent.user_model:get_user_profile")
    if isinstance(up, Exception): return _err(d, "import_um", up)
    d["parts"]["top_interests"] = sorted(up().get_profile().interests.items(),
                                          key=lambda kv: -kv[1])[:5]


def handle_optimize(d):
    diag = _imp("nexus_agent.self_optimization_diagnose:diagnose")
    if isinstance(diag, Exception): return _err(d, "diagnose", diag)
    r = diag()
    d["parts"]["diagnose"] = {"issues": r.get("issues", []),
                              "recs": r.get("recommendations", [])}
    sa = _imp("nexus_agent.self_awareness:get_self_awareness")
    if isinstance(sa, Exception): return _err(d, "import_sa", sa)
    try: d["parts"]["reflection"] = sa().reflect_on("optimization.diagnose", r)
    except Exception as e: _err(d, "reflect_on", e)


def handle_explore(q, d):
    domain = q.replace("能学", "").rstrip("??？? ").strip() or q
    up = _imp("nexus_agent.user_model:get_user_profile")
    if not isinstance(up, Exception): d["parts"]["top_3"] = up().get_top_interests(3)
    fw = _imp("nexus_agent.flywheel:run_flywheel")
    if isinstance(fw, Exception): return _err(d, "flywheel", fw)
    res = fw(domain); stages = res.get("stages", [])
    d["parts"]["flywheel"] = {"summary": res.get("summary", {}),
                              "elapsed_ms": res.get("elapsed_ms"),
                              "ok": sum(1 for s in stages if s.get("status") == "ok")}


H = {"self": lambda q, d, s: handle_self(d, s),
     "optimize": lambda q, d, s: handle_optimize(d),
     "explore": lambda q, d, s: handle_explore(q, d)}


def chat(query, show_state=False):
    intent = classify(query)
    d = {"parts": {}, "errors": {}}
    H[intent](query, d, show_state); p = d["parts"]
    if intent == "self":
        resp = p.get("express_state", "(no state)")
        ti = p.get("top_interests") or []
        if ti: resp += " | 兴趣=" + ",".join(k for k, _ in ti)
    elif intent == "optimize":
        dg = p.get("diagnose", {})
        resp = f"issues={len(dg.get('issues', []))} recs={dg.get('recs', [])}"
        if p.get("reflection"): resp += " | " + p["reflection"][:80]
    else:
        fw = p.get("flywheel", {})
        resp = f"flywheel ok={fw.get('ok', '?')}/8 elapsed={fw.get('elapsed_ms', '?')}ms top={p.get('top_3', [])}"
    return {"query": query, "intent": intent, "response": resp,
            "errors": d["errors"], "details": p}


def main():
    ap = argparse.ArgumentParser(description="Nexus 一行对话 (Stage 28)")
    ap.add_argument("--query", required=True)
    ap.add_argument("--show-state", action="store_true")
    a = ap.parse_args()
    print(json.dumps(chat(a.query, a.show_state), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()