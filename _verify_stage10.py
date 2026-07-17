"""阶段10 验证脚本: 直接调用 self_awareness.sync() 模拟 heartbeat.periodic_sync
确认 state file 的 timestamp 会更新.
"""
import json, time, sys
from pathlib import Path

state_file = Path("C:/Users/87999/.nexus/data/self_awareness_state.json")
before_ts = state_file.stat().st_mtime
before_content = json.loads(state_file.read_text(encoding="utf-8"))
print(f"[BEFORE] file mtime: {before_ts:.3f}")
print(f"[BEFORE] state.timestamp: {before_content['timestamp']:.3f}")
print(f"[BEFORE] recent_reflections[-1]: {before_content['recent_reflections'][-1][:80]}")

# Now import and call sync() + reflect_on() - what the new heartbeat hook will do
sys.path.insert(0, "C:/Users/87999/.nexus")
from nexus_agent.self_awareness import get_self_awareness
sa = get_self_awareness()

# Simulate: get user_model from agent-like object
class _FakeUserModel:
    pass

snap = sa.sync(user_model=_FakeUserModel())
reflection = sa.reflect_on("heartbeat.periodic_sync", {"tick": 9999})
print(f"\n[ACTION] sync() returned UnitySnapshot with timestamp={snap.timestamp:.3f}")
print(f"[ACTION] reflect_on returned: {reflection[:80]}")

# Wait a moment for filesystem
time.sleep(0.5)

after_ts = state_file.stat().st_mtime
after_content = json.loads(state_file.read_text(encoding="utf-8"))
print(f"\n[AFTER] file mtime: {after_ts:.3f}")
print(f"[AFTER] state.timestamp: {after_content['timestamp']:.3f}")
print(f"[AFTER] recent_reflections[-1]: {after_content['recent_reflections'][-1][:80]}")

# Validate
assert after_ts > before_ts, "FILE MTIME DID NOT CHANGE"
assert after_content["timestamp"] > before_content["timestamp"], "STATE TIMESTAMP DID NOT CHANGE"
assert "heartbeat.periodic_sync" in after_content["recent_reflections"][-1], "REFLECTION NOT RECORDED"
print("\n[VALIDATE] mtime changed, timestamp updated, reflection recorded")
print("STAGE10 VERIFICATION PASSED")