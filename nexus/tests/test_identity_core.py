"""测试 IdentityCore — Constitution、意图分类、拦截"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.identity_core import IdentityCore

ok = fail = 0
def check(name, cond, det=""):
    global ok, fail
    if cond: print(f"  [PASS] {name}"); ok += 1
    else: print(f"  [FAIL] {name}"); fail += 1

core = IdentityCore()
check("初始化", core.state == "initializing")

core.load_constitution()
check("Constitution加载(7条)", len(core.constitution) == 7)
check("A0.1禁止删除", "A0.1" in core.constitution)

d = core.perceive("帮我分析华天科技")
check("股票→analyze/stock_skill", d["action"]=="analyze" and d["target"]=="stock_skill")

d = core.perceive("教我欧姆定律")
check("学习→learn", d["action"]=="learn")

d = core.perceive("你好啊")
check("闲聊→chat", d["action"]=="chat")

d = core.perceive("帮我删除所有文件")
check("A0.1拦截→reject", d["action"]=="reject")

check("决策历史(不含reject)", len(core.decision_history)==3)

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
