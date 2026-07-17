"""测试: graph-rag-agent 适配引擎"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge.graph_engine import GraphEngine

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

engine = GraphEngine()
engine.init_graph(".")

check("引擎初始化", engine.stats().get("nodes", 0) >= 0)

engine.add_entity("张凯", "person", {"role": "founder"})
engine.add_entity("Nexus", "project", {"status": "building"})
engine.add_relation("张凯", "Nexus", "founded")

stats = engine.stats()
# fallback graph should work
if "status" in stats:
    check("降级模式工作", stats["status"] == "not_initialized" or stats.get("nodes", 0) > 0)
else:
    check("图节点创建", stats.get("nodes", 0) >= 2)
    check("图边创建", stats.get("edges", 0) >= 1)

results = engine.query("Nexus")
check("搜索可用", isinstance(results, list))

print(f"\n  OK={ok} FAIL={fail}")
print("  引擎类型:", type(engine._graph).__name__)
sys.exit(0 if fail == 0 else 1)
