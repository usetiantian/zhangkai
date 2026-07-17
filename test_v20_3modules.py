# -*- coding: utf-8 -*-
"""v20: 三个新模块集成测试"""
import sys, os
sys.path.insert(0, r"C:\Users\87999\.nexus")

PASS = 0; FAIL = 0
def test(name, condition, detail=""):
    global PASS, FAIL
    if condition: PASS += 1; print(f"  [PASS] {name}")
    else: FAIL += 1; print(f"  [FAIL] {name} — {detail}")

print("="*60)
print("v20 三模块集成测试")
print("="*60)

# ─── 1. EvaluationJudge ───
print("\n── 1. EvaluationJudge ──")
from nexus_agent.nexus_evaluation_judge import (
    get_evaluation_judge, ModificationProposal, EvaluationResult
)
judge = get_evaluation_judge()
test("get_evaluation_judge()", judge is not None)

# Test safety check
prop = ModificationProposal(
    file_path="nexus_agent/constitution.py",
    old_content="old", new_content="new", reason="test"
)
safe, reason = judge.safety_check(prop)
test("constitution.py 不可改", not safe)

prop2 = ModificationProposal(
    file_path="nexus_agent/heartbeat_loop.py",
    old_content="def test(): pass", new_content="def test(): return 42",
    reason="test fix"
)
safe2, _ = judge.safety_check(prop2)
test("heartbeat_loop.py 可以改", safe2)

# Test evaluation
result = judge.evaluate(prop2, domain="test")
test("evaluate() 返回结果", result is not None)
test("syntax check 通过", result.checks.get("syntax", False))
test("no_secrets check", result.checks.get("no_secrets", False))

# Test history
history = judge.get_history(5)
test(f"历史记录: {len(history)} 条", len(history) >= 1)

print(f"  Judge stats: {judge.stats()}")

# ─── 2. HebbianMemory ──
print("\n── 2. HebbianMemory ──")
from nexus_agent.nexus_hebbian import get_hebbian_memory
hm = get_hebbian_memory()
test("get_hebbian_memory()", hm is not None)

# Test record_access
hm.record_access("test_node_001")
test("record_access 不崩溃", True)

# Test apply_decay (first call might be cooldown)
result = hm.apply_decay()
test(f"apply_decay: {result.get('status', '?')}", result is not None)
test(f"tracked_nodes: {hm.stats().get('tracked_nodes', 0)}", hm.stats().get('tracked_nodes', 0) >= 1)

# Test boost_domain
try:
    hm.boost_domain("test_domain", 0.05)
    test("boost_domain 不崩溃", True)
except Exception as e:
    test("boost_domain", False, str(e)[:60])

# ─── 3. EmotionBridge ──
print("\n── 3. EmotionBridge ──")
from nexus_agent.nexus_emotion_bridge import get_emotion_bridge
eb = get_emotion_bridge()
test("get_emotion_bridge()", eb is not None)

# Test neutral mood
mood_neutral = {"dominant": "neutral", "intensity": 0.3}
weights = eb.update_from_mood(mood_neutral)
test(f"neutral→weights sum={sum(weights.values()):.2f}", abs(sum(weights.values()) - 1.0) < 0.01)
test(f"top_action: {eb.get_top_action()}", eb.get_top_action() in weights)

# Test achievement mood
mood_achievement = {"dominant": "achievement", "intensity": 0.9}
weights2 = eb.update_from_mood(mood_achievement)
test(f"achievement→explore boosted", weights2.get("explore", 0) > weights.get("explore", 0))
test(f"weights sum={sum(weights2.values()):.2f}", abs(sum(weights2.values()) - 1.0) < 0.01)

# Test safety mood
mood_safety_low = {"dominant": "safety", "intensity": 0.2}
weights3 = eb.update_from_mood(mood_safety_low)
test(f"safety_low→learn boosted", weights3.get("learn", 0) > weights.get("learn", 0))

print(f"  Bridge stats: {eb.stats()}")

# ─── 4. Integration: verify connected paths ───
print("\n── 4. 集成验证 ──")
import py_compile
integrated = [
    r"C:\Users\87999\.nexus\nexus_agent\evokg.py",
    r"C:\Users\87999\.nexus\nexus_agent\heartbeat_loop.py",
    r"C:\Users\87999\.nexus\nexus_agent\evolution_engine.py",
]
for p in integrated:
    try:
        py_compile.compile(p, doraise=True)
        test(f"compile {os.path.basename(p)}", True)
    except py_compile.PyCompileError as e:
        test(f"compile {os.path.basename(p)}", False, str(e)[:60])

# ─── Summary ───
print("\n" + "="*60)
print(f"  PASS: {PASS}  FAIL: {FAIL}")
if FAIL == 0: print("  全部通过!")
print("="*60)
