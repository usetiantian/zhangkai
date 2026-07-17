"""阶段10 验证脚本 3 (minimal):
直接调用 HeartbeatLoop.tick_count 自增 5 次, 让 mod 5 == 4 触发一次.
mock 所有重协程 (targeted_train, scenario_gen, training_executor),
只让 _self_awareness_sync 真跑.
"""
import asyncio, sys, json, time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, "C:/Users/87999/.nexus")

state_file = Path("C:/Users/87999/.nexus/data/self_awareness_state.json")
before_ts = state_file.stat().st_mtime
before_content = json.loads(state_file.read_text(encoding="utf-8"))
print(f"[BEFORE] state.timestamp: {before_content['timestamp']:.3f}")
print(f"[BEFORE] recent_reflections[-1]: {before_content['recent_reflections'][-1][:60]}")

from nexus_agent.self_awareness import get_self_awareness
agent = MagicMock()
agent.self_awareness = get_self_awareness()

from nexus_agent.heartbeat_loop import HeartbeatLoop
hb = HeartbeatLoop(agent=agent, cognitive_loop=None)
hb._running = True

# Patch _launch_async to capture and decide whether to actually run
import nexus_agent.heartbeat_loop as hbm
launched = []
original_launch = hb._launch_async

def _mock_launch(name, coro_fn):
    launched.append((name, coro_fn))
    # Only run the self_awareness_sync one
    if name == "self_awareness_sync":
        # Schedule immediately on the running loop
        if asyncio.iscoroutine(coro_fn):
            return asyncio.ensure_future(coro_fn)
        elif callable(coro_fn):
            return asyncio.ensure_future(coro_fn())
    # Skip everything else (return False so _task_running doesn't get stuck)
    return False

hb._launch_async = _mock_launch

# Now tick once with tick_count=3 (will become 4 after +=1 inside tick)
hb._tick_count = 3
asyncio.run(hb.tick())

# Wait for the captured sync to land
time.sleep(0.5)

# Inspect launched list
names = [n for n, _ in launched]
print(f"\n[LAUNCHED] {len(launched)} coroutines at tick #4:")
for n in names:
    marker = " <-- NEW" if n == "self_awareness_sync" else ""
    print(f"  - {n}{marker}")

assert "self_awareness_sync" in names, "self_awareness_sync was NOT scheduled"
print("\n[OK] self_awareness_sync coroutine was scheduled at tick #4")

after_ts = state_file.stat().st_mtime
after_content = json.loads(state_file.read_text(encoding="utf-8"))
print(f"\n[AFTER] state.timestamp: {after_content['timestamp']:.3f}")
print(f"[AFTER] recent_reflections[-1]: {after_content['recent_reflections'][-1][:60]}")

assert after_content["timestamp"] > before_content["timestamp"], "STATE TIMESTAMP DID NOT CHANGE"
assert any("heartbeat.periodic_sync" in r for r in after_content["recent_reflections"]), "REFLECTION NOT RECORDED"

print("\n[VALIDATE] self_awareness_sync hook fired at tick #4")
print("          state file timestamp updated to current time")
print("          'heartbeat.periodic_sync' reflection recorded")
print("\nSTAGE10 HEARTBEAT HOOK VERIFICATION PASSED")