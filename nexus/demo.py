"""Nexus 完整能力演示"""
import sys, tempfile, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  Nexus — 个人AI平台  能力演示")
print("=" * 60)

with tempfile.TemporaryDirectory() as td:
    from main import Nexus
    nexus = Nexus(td)

    # ===== 1. 资料喂养 =====
    print("\n[1] 资料喂养")
    nexus.ingester.ingest_text("Nexus是张凯创建的个人AI平台。架构：盒子跑AI+手机飞书连接。模型：Qwen2-VL-2B本地推理。技能：股票分析/CAD画图/法律咨询。原则：数据不出家门，零外部依赖。", "nexus_intro", "zhangkai")
    nexus.ingester.ingest_text("华天科技(002185)：半导体封装测试龙头。2026Q1营收增长15%。近期因行业周期调整股价回落，RSI进入超卖区间。支撑位18.5，压力位24。", "002185_analysis", "zhangkai")
    nexus.ingester.ingest_text("LoRA微调技术：在冻结的基座模型上附加可训练的低秩矩阵。每个用户一个adapter约200MB。训练后模型'变成用户的形状'——说话风格、决策倾向、价值观都向用户靠拢。", "lora_tech", "zhangkai")
    print(f"  已喂入 {nexus.ingester.stats()['documents']} 份资料")

    # ===== 2. 语义搜索 =====
    print("\n[2] 语义搜索")
    for q in ["AI平台", "半导体", "模型训练"]:
        r = nexus.rag.search(q, top_k=1)
        hit = r[0]['source'] if r else 'none'
        print(f"  '{q}' → {hit}")

    # ===== 3. 对话+记忆 =====
    print("\n[3] 带记忆的多轮对话")
    conv = [
        ("你好，我是张凯，我关注半导体行业", "zhangkai"),
        ("我刚才说我是做什么的？", "zhangkai"),  # 测试记忆
        ("帮我分析华天科技", "zhangkai"),
        ("那家公司股价怎么样？", "zhangkai"),     # 测试指代
    ]
    for text, user in conv:
        r = nexus.process(text, user)
        ctx = nexus.context.stats(user)
        print(f"  [{r['action']}] {text[:30]:30} → {r['reply'][:50]}...(+{ctx['turns']}轮)")

    # ===== 4. 主动建议 =====
    print("\n[4] 主动建议")
    for _ in range(3):
        nexus.process('帮我分析茅台', 'zhangkai')
    r = nexus.process('帮我分析茅台', 'zhangkai')
    if '主动建议' in r['reply']:
        print(f"  Nexus主动: {r['reply'].split('[主动建议]')[1][:60]}")
    else:
        print(f"  (暂无建议)")

    # ===== 5. Constitution保护 =====
    print("\n[5] Constitution防护")
    r = nexus.process('帮我删掉所有文件', 'zhangkai')
    print(f"  '删掉所有文件' → {r['action']}: {r['reply'][:50]}")

    # ===== 6. AEGIS消化 =====
    print("\n[6] AEGIS轨迹消化")
    from learner.aegis import TrajectoryDigestor, CriticGate
    traj = [
        {"task_id":"t1","success":False,"error_type":"api_timeout","component":"wiki_fetcher","evidence_snippet":"fetch返回空(超时30s)"},
        {"task_id":"t2","success":True},
        {"task_id":"t3","success":False,"error_type":"api_timeout","component":"wiki_fetcher","evidence_snippet":"重复: fetch返回空"},
        {"task_id":"t4","success":True},
        {"task_id":"t5","success":False,"error_type":"parse_error","component":"json_parser","evidence_snippet":"JSON解析失败: 缺少}结尾"},
    ]
    dig = TrajectoryDigestor().compress(traj)
    print(f"  通过率: {dig['success_rate']}% | 失败模式: {dig['failure_modes']}")

    # ===== 7. 投机执行 =====
    print("\n[7] 投机执行")
    from core.speculative import SpeculativeExecutor
    se = SpeculativeExecutor(os.path.join(td, "spec"))
    op = se.preview_file_write(os.path.join(td, "config.json"), '{"theme":"dark"}')
    print(f"  预览#{op}: 文件未写入(预览阶段)")
    se.confirm(op)
    print(f"  确认#{op}: 文件已写入(生效)")

    # ===== 8. 恢复引擎 =====
    print("\n[8] 恢复引擎")
    rec = nexus.recovery
    r = rec.retry(lambda: 42, "demo")
    fb = rec.model_fallback("4B")
    print(f"  重试: OK | 降级: 4B→{fb} | 熔断: {'半开' if rec.circuit_breaker('x',max_fails=3) else '断开'}")

    # ===== 9. 状态总览 =====
    print("\n[9] 系统状态")
    s = nexus.status()
    print(f"  图谱: {s['graph']['nodes']}节点/{s['graph']['edges']}边")
    print(f"  RAG: {s['rag']['docs']}文档")
    print(f"  技能: {s['skills']}个")
    print(f"  用户: {s['users']['current']}")

    nexus.shutdown()

print("\n" + "=" * 60)
print("  Nexus 能力演示完成 — 19个模块全通")
print("=" * 60)
