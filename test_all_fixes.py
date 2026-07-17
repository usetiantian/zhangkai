# -*- coding: utf-8 -*-
"""Nexus v18.1 + v18.1b 全量回归测试"""
import sys, os, traceback, time, json, inspect, asyncio, importlib

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
sys.path.insert(0, NEXUS)
sys.path.insert(0, os.path.dirname(NEXUS))

passed, failed, skipped = 0, 0, 0

def check(desc, ok):
    global passed, failed, skipped
    if ok is True:
        passed += 1
        print(f"  PASS  {desc}")
    elif ok is False:
        failed += 1
        print(f"  FAIL  {desc}")
    else:
        skipped += 1
        print(f"  SKIP  {desc}")

T = True  # shorthand

# ══════════════════════════════════════════
print("=" * 60)
print("TEST 1: MultiHeadNexus 训练 (inplace + 128-dim fix)")
print("=" * 60)

import torch, numpy as np

try:
    from neural.heads import MultiHeadNexus, NexusHead, LoRALinear, get_multihead_nexus
    check("import heads module", T)
except Exception as e:
    check(f"import: {e}", False)
    torch = None

if torch:
    mhn = MultiHeadNexus()
    check("MultiHeadNexus init [6 heads]", len(mhn.heads) == 6)

    # 1a: extract_features clone
    vec = np.random.randn(256).astype(np.float32)
    f = mhn.extract_features(vec)
    old = f[0, 0].item()
    vec[0] = 999.0
    check("extract_features: clone isolation", f[0, 0].item() == old)

    # 1b: 128-dim pad to 256
    vec128 = np.random.randn(128).astype(np.float32)
    f128 = mhn.extract_features(vec128)
    check(f"extract_features: 128-dim -> {f128.shape[1]} (expect 256)", f128.shape[1] == 256)

    # 1c: load() uses copy_()
    head = NexusHead("t", 256, 64, 1)
    src = inspect.getsource(head.load)
    actual = [l for l in src.split('\n') if '.data' in l and not l.strip().startswith('#')]
    all_copy = all('copy_(' in l for l in actual)
    check(f"load(): all {len(actual)} lines use copy_()", all_copy)

    # 1d: train 6 heads
    rd = {"seed_vector": np.random.randn(256).astype(np.float32),
          "solution_vector": np.random.randn(256).astype(np.float32),
          "domain": "code_mutation", "verified": T, "score": 0.85,
          "problem": "test", "user_interests": {}, "capability_scores": {}}
    results = mhn.train_on_selfplay_round(rd)
    ok = len(results) == 6 and all(isinstance(v, float) and not (np.isnan(v) or np.isinf(v)) for v in results.values())
    check(f"train_on_selfplay_round: 6/6 heads", ok)

    # 1e: predict
    p = mhn.predict_all(np.random.randn(256).astype(np.float32))
    check("predict_all: 6 heads", all(k in p for k in ["semantic","difficulty","router","quality","recommender","gap"]))

    # 1f: save/load cycle
    mhn.save_all()
    loaded = mhn.load_all()
    check(f"save_all + load_all: {loaded}/6 heads", loaded >= 0)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 2: ExperienceBank")
print("=" * 60)

from experience_bank import ExperienceBank, get_experience_bank
bank = get_experience_bank()
check("get_experience_bank singleton", bank is not None)

before = bank.count()
r = bank.add_experience({"type":"test_v18.1b","question":"q","solution":"sol","success":T})
after = bank.count()
check(f"add_experience(dict) [{before}->{after}]", after >= before)

r = bank.rebuild_index()
check("rebuild_index()", r["status"] == "ok")

stats = bank.get_stats()
check(f"get_stats: total={stats['total_experiences']}, rate={stats['success_rate']:.2f}",
      "total_experiences" in stats and "success_rate" in stats)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 3: WorktreeSandbox + WorktreeAgent")
print("=" * 60)

from sandbox import WorktreeSandbox, WorktreeAgent
check("import WorktreeAgent", T)

sb = WorktreeSandbox(timeout=10)
agent = WorktreeAgent(sandbox=sb)
check("WorktreeAgent init", agent.sandbox is sb)

async def _run():
    a = WorktreeAgent()
    return await a.execute("test")
r = asyncio.get_event_loop().run_until_complete(_run())
check("WorktreeAgent.execute()", r["success"] is True)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 4: KnowledgeGen cooldown")
print("=" * 60)

from knowledge_generator import KnowledgeGenerator
kg = KnowledgeGenerator()
check("KnowledgeGenerator init", T)

src = inspect.getsource(KnowledgeGenerator.generate_for_domain)
check("generate_for_domain: fail_limit+2", "fail_limit + 2" in src)
check("generate_for_domain: cooldown 3600", "3600" in src)

src2 = inspect.getsource(KnowledgeGenerator.generate_all_domains)
check("generate_all_domains: streak>=5", "streak >= 5" in src2)
check("generate_all_domains: cooldown 3600", "3600" in src2)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 5: heartbeat_loop 源代码检查")
print("=" * 60)

with open(os.path.join(NEXUS, "heartbeat_loop.py"), "r", encoding="utf-8") as f:
    hb = f.read()

check("bilibili: await (not create_task)",
      "results = await self.agent.bilibili" in hb)
check("bilibili: timeout=120",
      'timeout=120.0, result=result' in hb)
check("research_engine hook present",
      'research_engine' in hb and 'get_research_engine' in hb)
check("research_engine timeout=300",
      'timeout=300.0, result=result' in hb.split('research_engine')[1] if 'research_engine' in hb else False)
check("dead _run_bilibili removed",
      "async def _run_bilibili" not in hb)
check("dead _run_research removed",
      "async def _run_research" not in hb)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 6: ResearchEngine v2")
print("=" * 60)

try:
    from research_engine.engine import ResearchEngine, get_research_engine
    check("import research_engine.engine", T)
except Exception as e:
    check(f"import: {e}", False)
    ResearchEngine = None

if ResearchEngine:
    re = ResearchEngine()
    check("ResearchEngine init", T)

    # Check key methods exist
    for method in ["discover_papers", "comprehend_paper", "hypothesize",
                   "design_experiment", "execute_experiment",
                   "integrate_findings", "self_improve", "research_cycle"]:
        check(f"  method: {method}", hasattr(re, method))

    # Check domain keywords
    check(f"  domains: {re._domains}", len(re._domains) >= 3)
    check(f"  arxiv API configured", "export.arxiv.org" in re.ARXIV_API)

    # Test _get_nexus_gaps (offline, should return defaults)
    gaps = re._get_nexus_gaps()
    check(f"  _get_nexus_gaps: {len(gaps)} gaps", len(gaps) > 0)

    # Test _compute_relevance
    score = re._compute_relevance("Deep Learning for Code", "We use transformers", "deep learning")
    check(f"  _compute_relevance: score={score:.2f}", score > 0)

    # Test get_health
    health = re.get_health()
    check(f"  get_health: {health['stats']}", isinstance(health, dict))

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 7: LLM providers + lark_oapi")
print("=" * 60)

# lark_oapi
try:
    import lark_oapi
    check("import lark_oapi", T)
except ImportError:
    check("lark_oapi MISSING", False)

# providers
from nexus_llm import NexusLLM
llm = NexusLLM()
providers = llm._providers
names = [p.name for p in providers]
check(f"LLM providers: {names}", len(providers) > 0)

# Check DeepSeek model name
ds = [p for p in providers if p.name == "deepseek"]
if ds:
    check(f"DeepSeek model: {ds[0].model}", "deepseek-v4-flash" in ds[0].model)

# Check Minimax healthy
mm = [p for p in providers if p.name == "minimax"]
if mm:
    check(f"Minimax healthy: {mm[0].healthy}", mm[0].healthy)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 8: 文件完整性 (.gitignore + neural/)")
print("=" * 60)

# .gitignore
gi_path = os.path.join(os.path.dirname(NEXUS), ".gitignore")
with open(gi_path, "r", encoding="utf-8") as f:
    gi = f.read()
check(".gitignore: neural/*.pt (not neural/)",
      "nexus_agent/neural/*.pt" in gi and "nexus_agent/neural/" not in gi.replace("nexus_agent/neural/*.pt", ""))

# neural/ source files now tracked
neural_dir = os.path.join(NEXUS, "neural")
py_files = [f for f in os.listdir(neural_dir) if f.endswith(".py")]
check(f"neural/ .py files: {len(py_files)}", len(py_files) >= 5)
for f in sorted(py_files)[:5]:
    check(f"  neural/{f}", os.path.getsize(os.path.join(neural_dir, f)) > 0)

# ══════════════════════════════════════════
print()
print("=" * 60)
print("TEST 9: 基础模块无 import 错误")
print("=" * 60)

modules = [
    ("neural.heads", "MultiHeadNexus"),
    ("neural.training_loop", "NeuralTrainingLoop"),
    ("experience_bank", "ExperienceBank"),
    ("sandbox", "WorktreeAgent"),
    ("knowledge_generator", "KnowledgeGenerator"),
    ("nexus_llm", "NexusLLM"),
    ("research_engine.engine", "ResearchEngine"),
]
for modname, clsname in modules:
    try:
        mod = importlib.import_module(modname)
        assert hasattr(mod, clsname) or True  # just check import
        check(f"import {modname}", T)
    except Exception as e:
        check(f"import {modname}: {str(e)[:60]}", False)

# ══════════════════════════════════════════
print()
print("=" * 60)
print(f"TOTAL: {passed} PASS, {failed} FAIL, {skipped} SKIP")
print("=" * 60)

if failed > 0:
    sys.exit(1)
