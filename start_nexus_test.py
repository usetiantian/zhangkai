"""Stage 28: nexus_daemon 真启动验证 (import-only, 不开后台进程).

任务原文用"_init_user_model", 但实测 NexusAgent 的 init 流水是:
  _init_self_awareness   → agent.self_awareness
  _init_user_profile     → agent.user_profile  + agent.user_store
  _init_user_model_engine→ agent.user_model_engine
三处都直接调,绕开 init_fully (避免心跳/事件桥/timer爆炸).

验证点:
  1. import nexus_agent.run_agent 不报错
  2. 实例化 NexusAgent 不触发飞书/LLM
  3. agent.self_awareness 真存在,express_state() 输出非空
  4. agent.user_profile   真存在; agent.user_model_engine 真存在
  5. nexus_status 4 CLI 命令 (subprocess.run all/self/diagnose/stats)
"""
from __future__ import annotations
import os, sys, json, time, subprocess, tracemalloc
from pathlib import Path

NEXUS_ROOT = Path(r"C:\Users\87999\.nexus")
sys.path.insert(0, str(NEXUS_ROOT)) if NEXUS_ROOT.exists() else None
WS = Path(r"C:\Users\87999\claude-workspace")

def run_test() -> dict:
    tracemalloc.start()
    t0 = time.perf_counter()
    out = {"agent_inited": False, "all_exports_work": False,
           "status_outputs": [], "errors": []}
    try:
        from nexus_agent.run_agent import NexusAgent  # 1) import
        from nexus_agent.agent_init import (_init_self_awareness,  # 2) init fns
                                            _init_user_profile)
    except Exception as e:
        out["errors"].append(f"import: {type(e).__name__}: {e}")
        return out
    agent = NexusAgent()                                        # 3) 实例化
    try:
        _init_self_awareness(agent)
        _init_user_profile(agent)
        out["agent_inited"] = (getattr(agent, "self_awareness", None) is not None
                               and getattr(agent, "user_profile", None) is not None)
    except Exception as e:
        out["errors"].append(f"init: {type(e).__name__}: {e}")
    # 4) express_state
    try:
        state = agent.self_awareness.express_state()
        out["express_state"] = state[:200]
    except Exception as e:
        out["errors"].append(f"express_state: {e}")
    # 5) user_model_engine — agent_init._init_user_model_engine 真正设的属性名
    try:
        from nexus_agent.agent_init import _init_user_model_engine
        _init_user_model_engine(agent)
        out["has_user_model_engine"] = getattr(agent, "user_model_engine", None) is not None
    except Exception as e:
        out["has_user_model_engine"] = False
        out["errors"].append(f"user_model_engine: {e}")
    # 6) nexus_status CLI × 4
    for cmd in ("all", "self", "diagnose", "stats"):
        try:
            r = subprocess.run([sys.executable, str(WS / "nexus_status.py"), cmd],
                               capture_output=True, text=True, timeout=30,
                               cwd=str(WS))
            out["status_outputs"].append(
                {"cmd": cmd, "rc": r.returncode,
                 "stdout_head": (r.stdout or "")[:160],
                 "stderr_head": (r.stderr or "")[:160]})
        except Exception as e:
            out["status_outputs"].append({"cmd": cmd, "err": str(e)})
    out["all_exports_work"] = out["agent_inited"] and not out["errors"]
    out["elapsed_s"] = round(time.perf_counter() - t0, 2)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    out["mem_peak_kb"] = round(peak / 1024, 1)
    return out

if __name__ == "__main__":
    print(json.dumps(run_test(), ensure_ascii=False, indent=2))
