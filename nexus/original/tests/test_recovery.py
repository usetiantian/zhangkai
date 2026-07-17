import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from recovery import RecoverySystem

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

r = RecoverySystem()

# 层1: 重试成功
result = r.retry_with_backoff(lambda: 42, "test_success", max_retries=3)
check("层1重试成功", result == 42)

# 层2: fallback
check("层2切本地模型", r.switch_to_local("overload")["model"] == "qwen_local")

# 层3: 压缩触发
check("层3触发压缩(超阈值)", r.compact_if_needed(12000, 10000))
check("层3不触发(未超)", not r.compact_if_needed(5000, 10000))

# 层5: 模型降级
check("层5: 4B->2B", r.model_fallback("4B") == "2B")
check("层5: 2B->rules", r.model_fallback("2B") == "rules")

# 层6: 持久重试
check("层6第1次OK", r.persistent_retry("learn_task", max_attempts=3))
check("层6第2次OK", r.persistent_retry("learn_task", max_attempts=3))
check("层6第3次OK", r.persistent_retry("learn_task", max_attempts=3))
check("层6超限", not r.persistent_retry("learn_task", max_attempts=3))

# 层7: 熔断器
check("层7初始闭合", r.circuit_breaker("api_key"))
for _ in range(5): r.record_failure("api_key")
check("层7五次失败断开", not r.circuit_breaker("api_key"))

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
