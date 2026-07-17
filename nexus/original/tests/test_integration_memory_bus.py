"""综合测试：EventBus + IdentityCore + 五层记忆 — 10项"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.event_bus import bus
from core.identity_core import IdentityCore
from memory.short_term import ShortTermMemory
from memory.working import WorkingMemory
from memory.long_term import LongTermMemory
from memory.summary import SummaryMemory
from memory.checkpoint import Checkpoint
from knowledge.graph import KnowledgeGraph

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

with tempfile.TemporaryDirectory() as td:
    core = IdentityCore()
    stm = ShortTermMemory()
    wm = WorkingMemory()
    ltm = LongTermMemory(KnowledgeGraph(), td)
    sm = SummaryMemory()
    ckpt = Checkpoint(os.path.join(td, "checkpoint.json"))

    bus.subscribe("user.message", lambda d: stm.add("user", d["text"]), "memory")
    bus.subscribe("user.message", lambda d: core.perceive(d["text"]), "identity")
    bus.publish("user.message", {"text": "帮我分析华天科技", "source": "feishu"})
    check("1.短期记忆记录", stm.summary()["total_turns"] >= 1)
    check("2.身份核心感知", core.decision_history[-1]["action"] == "analyze")

    d = core.perceive("帮我画个户型图")
    bus.subscribe("identity.decision", lambda x: wm.set_task(x["action"], x["target"]), "working")
    bus.publish("identity.decision", d, source="identity")
    check("3.工作记忆任务", wm.current_task["action"] == "skill")

    wm.set_speculative("/tmp/test.json", "preview")
    check("4.投机预览", wm.snapshot()["speculative_count"] == 1)
    wm.clear_speculative("/tmp/test.json", False)
    check("5.取消投机", wm.snapshot()["speculative_count"] == 0)

    ltm.remember_user("zhangkai", "style", "游资")
    check("6.长期记忆存储", ltm.get_user_preferences("zhangkai") == {"style": "游资"})

    sm.add("Nexus架构讨论", ["EventBus", "五层记忆", "零依赖"], 15)
    check("7.摘要记忆存储", len(sm.summaries) == 1)

    ckpt.save({"last_action": "analyze", "module_states": {"identity": "ok"}})
    restored = ckpt.load()
    check("8.checkpoint保存", ckpt.exists())
    check("9.checkpoint恢复", restored["last_action"] == "analyze")
    check("10.模块状态保留", restored["module_states"]["identity"] == "ok")

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
