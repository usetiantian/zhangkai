import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.event_bus import bus
from core.identity_core import IdentityCore

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: print(f"  [PASS] {name}"); ok += 1
    else: print(f"  [FAIL] {name}"); fail += 1

core = IdentityCore()

# 连接1
decisions = []
bus.subscribe("identity.decision", lambda d: decisions.append(d), "test")
d = core.perceive("帮我分析股票")
bus.publish("identity.decision", d, source="identity_core")
check("identity→module", len(decisions)==1 and decisions[0]["action"]=="analyze")

# 连接2: 外部输入桥→身份核心
before = len(core.decision_history)
bus.subscribe("perception.input", lambda d: core.perceive(d["text"]), "identity_core")
bus.publish("perception.input", {"text": "你好", "source": "feishu"}, source="bridge")
check("bridge→identity", len(core.decision_history) > before)

# 连接3: 模块死亡
bus.module_dead("qwen_model")
check("死亡通知", not bus.is_alive("qwen_model"))

print(f"  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
