import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge.graph import KnowledgeGraph
from memory.long_term import LongTermMemory

ok = fail = 0
def check(n, c):
    global ok, fail
    if c: print(f"  [PASS] {n}"); ok += 1
    else: print(f"  [FAIL] {n}"); fail += 1

with tempfile.TemporaryDirectory() as td:
    ltm = LongTermMemory(KnowledgeGraph(), td)
    ltm.remember_user("zhangkai", "style", "游资")
    ltm.remember_user("zhangkai", "verbose", "简洁")
    ltm.remember_project("nexus", "arch", "box+phone")

    check("用户偏好保存", ltm.graph.stats()["nodes"] >= 3)
    check("偏好读取", ltm.get_user_preferences("zhangkai") == {"style":"游资","verbose":"简洁"})

    ltm.write_diary("2026-07-17", "今日开始构建新Nexus架构")
    diary = ltm.read_diary("2026-07-17")
    check("日记写入+读取", "新Nexus架构" in diary)

    # 持久化测试——保存到 temp 目录内
    save_path = os.path.join(td, "ltm_graph.json")
    ltm.save(save_path)
    ltm2 = LongTermMemory.load(td, graph_path=save_path)
    check("持久化恢复", ltm2.get_user_preferences("zhangkai") == {"style":"游资","verbose":"简洁"})

print(f"\n  OK={ok} FAIL={fail}")
sys.exit(0 if fail == 0 else 1)
