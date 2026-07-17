"""测试 EventBus — 正常通信、故障隔离、死亡通知"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.event_bus import bus

ok_count = 0
fail_count = 0

def check(name, condition, detail=""):
    global ok_count, fail_count
    if condition:
        print(f"  [PASS] {name}  {detail}")
        ok_count += 1
    else:
        print(f"  [FAIL] {name}  {detail}")
        fail_count += 1

# Test 1: 正常发布订阅
received = []
def h1(data): received.append(data)
bus.subscribe("test.hello", h1, "module_a")
bus.publish("test.hello", {"msg": "world"}, source="test")
check("pub/sub通信", len(received)==1 and received[0]["msg"]=="world", str(received))

# Test 2: 故障隔离
good = []
def h_ok(data): good.append(data)
def h_bad(data): raise RuntimeError("boom")
bus.subscribe("test.fault", h_ok, "module_good")
bus.subscribe("test.fault", h_bad, "module_bad")
bus.publish("test.fault", {"x": 1}, source="test")
check("故障隔离", len(good)==1 and good[0]["x"]==1, f"收到{len(good)}条, 不受坏handler影响")

# Test 3: 死亡通知
dead = []
def on_dead(data): dead.append(data["module"])
bus.subscribe("module.dead", on_dead, "monitor")
bus.module_dead("module_x")
check("死亡通知", len(dead)==1 and dead[0]=="module_x", str(dead))

# Test 4: 重复订阅不重复触发
double = []
def dh(data): double.append(data)
bus.subscribe("test.double", dh, "mod_a")
bus.subscribe("test.double", dh, "mod_b")  # 不同模块可以同名订阅
bus.publish("test.double", {"n": 2}, source="test")
check("多订阅者", len(double)==2 and double[0]["n"]==2 and double[1]["n"]==2, f"收到{len(double)}条")

print(f"\n  OK={ok_count} FAIL={fail_count}")
sys.exit(0 if fail_count == 0 else 1)
