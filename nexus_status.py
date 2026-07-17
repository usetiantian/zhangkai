"""nexus_status.py — Nexus 自我报告 CLI. Usage: all|self|diagnose|stats"""
from __future__ import annotations
import sys
from pathlib import Path

NEXUS_ROOT = Path("C:/Users/87999/.nexus")
sys.path.insert(0, str(NEXUS_ROOT)) if NEXUS_ROOT.exists() else None

CAPS = [("自我意识","self_awareness"),("自主学习","auto_learner"),
        ("自主思考","decision_engine"),("自主进化","evolution_engine"),
        ("自主优化","self_optimization"),("自我改代码","self_modifier"),
        ("世界模型","world_model_v19"),("个性化","user_model")]
def _try(mod):
    try: __import__(f"nexus_agent.{mod}"); return "✓"
    except ImportError as e: return f"✗({type(e).__name__})"
    except Exception as e: return f"~({type(e).__name__})"
def _hdr(t): print(f"{'='*60}\nNexus 自我报告 — {t}\n{'='*60}")


def cmd_all():
    _hdr("ALL")
    print("[1/3] 8 项能力:")
    for lab, mod in CAPS:
        print(f"  {_try(mod)} {lab} ({mod})")
    print("\n[2/3] 基础设施:")
    for n, p in [("data/", NEXUS_ROOT/"data"), ("kernel/", NEXUS_ROOT/"kernel"),
                 ("nexus_agent/", NEXUS_ROOT/"nexus_agent"),
                 ("self_awareness/", NEXUS_ROOT/"nexus_agent/self_awareness")]:
        print(f"  {'✓' if p.exists() else '✗'} {n}")
    print("\n[3/3] 全栈验证:")
    try:
        from nexus_agent.self_awareness import get_self_awareness
        s = get_self_awareness().sync()
        print(f"  ✓ sync() unity={s.unity_score:.2f} doms={len(s.known_domains)}")
    except Exception as e:
        print(f"  ✗ sync() {type(e).__name__}: {e}")
    try:
        from nexus_agent.self_optimization_diagnose import diagnose
        d = diagnose()
        print(f"  ✓ diagnose() issues={len(d['issues'])} recs={len(d['recommendations'])}")
    except Exception as e:
        print(f"  ✗ diagnose() {type(e).__name__}: {e}")
    try:
        from nexus_agent.capability_tree import get_capability_tree
        s = get_capability_tree().get_status()
        print(f"  ✓ cap_tree cats={s['categories']} skills={s['total_skills']} mastered={s['mastered']}")
    except Exception as e:
        print(f"  ✗ cap_tree {type(e).__name__}: {e}")
def cmd_self():
    _hdr("SELF (express_state)")
    from nexus_agent.self_awareness import get_self_awareness
    print(get_self_awareness().express_state())


def cmd_diagnose():
    _hdr("DIAGNOSE")
    from nexus_agent.self_optimization_diagnose import diagnose
    d = diagnose()
    print(f"issues ({len(d['issues'])}):")
    for i, x in enumerate(d["issues"], 1):
        print(f"  [{i}] {x}")
    print(f"recommendations ({len(d['recommendations'])}):")
    [print(f"  → {r}") for r in d["recommendations"]]


def cmd_stats():
    _hdr("STATS")
    try:
        from nexus_agent.evokg import get_evokg
        s = get_evokg().get_stats()
        print(f"知识图谱: nodes={s.get('total_nodes', 0)} edges={s.get('total_edges', 0)}")
    except Exception as e:
        print(f"  ✗ EvoKG: {type(e).__name__}: {e}")
    try:
        from nexus_agent.capability_tree import get_capability_tree
        s = get_capability_tree().get_status()
        print(f"能力树: cats={s.get('categories', 0)} skills={s.get('total_skills', 0)} "
              f"mastered={s.get('mastered', 0)} known={s.get('known', 0)}")
    except Exception as e:
        print(f"  ✗ CapabilityTree: {type(e).__name__}: {e}")
    try:
        from nexus_agent.self_awareness import get_self_awareness
        sa = get_self_awareness()
        ms = [m for m in dir(sa) if not m.startswith("_") and callable(getattr(sa, m))]
        print(f"自我意识接口: {len(ms)} 个 — {ms}")
    except Exception as e:
        print(f"  ✗ SelfAwareness: {type(e).__name__}: {e}")


def main():
    cmds = {"all": cmd_all, "self": cmd_self, "diagnose": cmd_diagnose, "stats": cmd_stats}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[sys.argv[1]]()


if __name__ == "__main__":
    main()