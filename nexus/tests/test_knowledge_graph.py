import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge.graph import KnowledgeGraph

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: print(f"  [PASS] {name}"); ok += 1
    else: print(f"  [FAIL] {name}"); fail += 1

kg = KnowledgeGraph()

# 节点操作
kg.add_node("zhangkai", "张凯", "person", role="founder")
kg.add_node("nexus", "Nexus", "project", status="building")
check("节点创建", kg.stats()["nodes"] == 2)

n = kg.get_node("zhangkai")
check("获取节点", n["name"] == "张凯")

r = kg.find_by_name("张凯")
check("按名查找", len(r) == 1 and r[0]["role"] == "founder")

# 关系操作
kg.add_edge("zhangkai", "nexus", "founded")
check("边创建", kg.stats()["edges"] == 1)

nbs = kg.get_neighbors("zhangkai")
check("查邻居(out)", len(nbs) == 1 and nbs[0]["relation"] == "founded")

nbs2 = kg.get_neighbors("nexus", direction="in")
check("查邻居(in)", len(nbs2) == 1 and nbs2[0]["relation"] == "founded")

# 搜索
kg.add_node("stock", "股票分析", "skill")
r = kg.search("股票")
check("关键词搜索", len(r) == 1 and r[0]["name"] == "股票分析")

# 持久化
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    tmp = f.name
kg.save(tmp)
kg2 = KnowledgeGraph.load(tmp)
os.unlink(tmp)
check("保存+恢复", kg2.stats()["nodes"] == 3 and kg2.stats()["edges"] == 1)

# 幂等性
kg.add_node("zhangkai", "张凯233", "person", new_field="test")
check("幂等更新", "new_field" in kg.get_node("zhangkai"))
check("名称不变", kg.get_node("zhangkai")["name"] == "张凯")

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
