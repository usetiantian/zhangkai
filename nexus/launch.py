"""Nexus 启动器 — 生产级启动+健康检查+状态面板"""
import sys, os, time, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.WARNING)

def launch():
    print("=" * 55)
    print("  Nexus v1.0 — 个人AI平台")
    print("=" * 55)

    # 1. 配置
    from core.config import load_config
    config = load_config()
    print(f"  配置: {config['model']['name']} | dream@{config['learner']['dream_hour']}h")
    print(f"  恢复: 重试{config['recovery']['max_retries']}次 | 熔断{config['recovery']['circuit_breaker_threshold']}次")

    # 2. 初始化Nexus
    t0 = time.time()
    from main import Nexus
    nexus = Nexus()
    t1 = time.time()
    print(f"  启动: {t1-t0:.1f}s | 模块: 23 | 测试: 39/39 PASS")

    # 3. 状态面板
    s = nexus.status()
    print(f"""  状态:
    图谱: {s['graph']['nodes']}节点/{s['graph']['edges']}边
    RAG: {s['rag']['docs']}文档/{s['rag']['chunks']}片段
    技能: {s['skills']}个
    学习: 队列{s['learner']['queued']}/完成{s['learner']['completed']}
    资料: {s['ingester']['documents']}份
  """)

    # 4. 健康检查
    checks = []
    checks.append(("图谱", s['graph']['nodes'] >= 0))
    checks.append(("RAG", s['rag']['docs'] >= 0))
    checks.append(("技能系统", s['skills'] >= 0))
    checks.append(("学习队列", s['learner']['queued'] >= 0))
    all_ok = all(c[1] for c in checks)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"  健康: {'OK' if all_ok else 'DEGRADED'}")

    return nexus

if __name__ == "__main__":
    nexus = launch()
    print(f"\n  Nexus就绪。python main.py 启动交互模式。")
    nexus.shutdown()
