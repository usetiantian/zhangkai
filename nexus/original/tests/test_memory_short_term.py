import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memory.short_term import ShortTermMemory

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

m = ShortTermMemory(max_turns=5)
check("初始化", m.summary()["total_turns"] == 0)

m.add("user", "今天天气真好")
m.add("nexus", "是啊，适合出去走走")
check("添加对话", m.summary()["total_turns"] == 2)
check("最后用户消息", m.get_last_user_message() == "今天天气真好")

ctx = m.get_context()
check("获取上下文", len(ctx) == 2)
check("角色正确", ctx[0]["role"] == "user" and ctx[1]["role"] == "nexus")

# 超容量测试
for i in range(10):
    m.add("user", f"消息{i}")
check("容量限制(最多5条)", len(m.get_context()) == 5)

m.clear()
check("清空", m.summary()["total_turns"] == 0)

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
