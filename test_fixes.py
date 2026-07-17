# -*- coding: utf-8 -*-
"""Nexus v18.1 fix verification tests"""
import sys, os, traceback, time, json, inspect, asyncio

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
        print(f"  SKIP  {desc} -- {ok}")

# === TEST 1: MultiHeadNexus ===
print("=" * 50)
print("TEST 1: MultiHeadNexus inplace fix")
try:
    import torch, numpy as np
    from neural.heads import MultiHeadNexus, get_multihead_nexus, NexusHead, LoRALinear
    check("import heads module", True)
except Exception as e:
    check(f"import: {e}", False)
    torch = None

if torch:
    try:
        mhn = MultiHeadNexus()
        assert len(mhn.heads) == 6
        check("MultiHeadNexus init [6 heads]", True)
    except Exception as e:
        check(f"init: {e}", False)
        mhn = None

    if mhn:
        try:
            vec = np.random.randn(256).astype(np.float32)
            f = mhn.extract_features(vec)
            old = f[0, 0].item()
            vec[0] = 999.0
            assert f[0, 0].item() == old, "clone broken!"
            check("extract_features clones (no mem share)", True)
        except Exception as e:
            check(f"extract_features: {e}", False)

        try:
            head = NexusHead("test", 256, 64, 1)
            src = inspect.getsource(head.load)
            assert "copy_(" in src
            assert ".data =" not in src
            check("load() uses copy_() not .data =", True)
        except Exception as e:
            check(f"load check: {e}", False)

        try:
            rd = {"seed_vector": np.random.randn(256).astype(np.float32),
                  "solution_vector": np.random.randn(256).astype(np.float32),
                  "domain": "code_mutation", "verified": True, "score": 0.85,
                  "problem": "test", "user_interests": {}, "capability_scores": {}}
            results = mhn.train_on_selfplay_round(rd)
            assert len(results) == 6, f"got {len(results)}"
            for n, v in results.items():
                assert isinstance(v, float) and not (np.isnan(v) or np.isinf(v)), f"{n}={v}"
            check("train_on_selfplay_round: 6/6 heads trained", True)
        except Exception as e:
            check(f"train: {e}", False)

        try:
            p = mhn.predict_all(np.random.randn(256).astype(np.float32))
            for k in ["semantic","difficulty","router","quality","recommender","gap"]:
                assert k in p
            check("predict_all: all 6 heads OK", True)
        except Exception as e:
            check(f"predict: {e}", False)

# === TEST 2: ExperienceBank ===
print()
print("=" * 50)
print("TEST 2: ExperienceBank methods")
try:
    from experience_bank import ExperienceBank, get_experience_bank
    bank = get_experience_bank()
    check("import + get_instance", True)
except Exception as e:
    check(f"import: {e}", False)
    bank = None

if bank:
    try:
        before = bank.count()
        r = bank.add_experience({"type":"test","question":"q","solution":"sol","success":True})
        after = bank.count()
        assert after >= before
        check(f"add_experience(dict) [{before}->{after}]", True)
    except Exception as e:
        check(f"add_experience: {e}", False)

    try:
        r = bank.rebuild_index()
        assert r["status"] == "ok"
        check("rebuild_index()", True)
    except Exception as e:
        check(f"rebuild_index: {e}", False)

    try:
        stats = bank.get_stats()
        check(f"get_stats: total={stats['total_experiences']}", True)
    except Exception as e:
        check(f"get_stats: {e}", False)

# === TEST 3: WorktreeSandbox ===
print()
print("=" * 50)
print("TEST 3: WorktreeSandbox + WorktreeAgent")
try:
    from sandbox import WorktreeSandbox, WorktreeAgent
    check("import WorktreeAgent", True)
except Exception as e:
    check(f"import: {e}", False)

try:
    sb = WorktreeSandbox(timeout=10)
    agent = WorktreeAgent(sandbox=sb)
    assert agent.sandbox is sb
    check("WorktreeAgent init", True)
except Exception as e:
    check(f"agent init: {e}", False)

try:
    sb2 = WorktreeSandbox(timeout=10)
    wd = sb2.create()
    assert os.path.exists(wd)
    sb2.cleanup()
    check("create + cleanup", True)
except Exception as e:
    check(f"sandbox ops: {e}", False)

try:
    async def _run():
        a = WorktreeAgent()
        return await a.execute("test")
    r = asyncio.get_event_loop().run_until_complete(_run())
    assert r["success"]
    check("execute() stub", True)
except Exception as e:
    check(f"execute: {e}", False)

# === TEST 4: KnowledgeGen ===
print()
print("=" * 50)
print("TEST 4: KnowledgeGen cooldown")
try:
    from knowledge_generator import KnowledgeGenerator
    kg = KnowledgeGenerator()
    check("import knowledge_generator", True)
except Exception as e:
    check(f"import: {e}", False)

try:
    src = inspect.getsource(KnowledgeGenerator.generate_for_domain)
    assert "fail_limit + 2" in src
    assert "3600" in src
    check("cooldown: fail_limit+2 (5), base=3600", True)
except Exception as e:
    check(f"cooldown check: {e}", False)

try:
    src2 = inspect.getsource(KnowledgeGenerator.generate_all_domains)
    assert "streak >= 5" in src2
    check("generate_all_domains: streak>=5", True)
except Exception as e:
    check(f"gen_all check: {e}", False)

# === TEST 5: LLM Providers ===
print()
print("=" * 50)
print("TEST 5: LLM providers")
try:
    from nexus_llm import NexusLLM, LLMProvider
    llm = NexusLLM()
    providers = llm._load_providers()
    names = [p.name for p in providers]
    check(f"providers: {names}", len(providers) > 0)
except Exception as e:
    check(f"providers: {e}", False)
    providers = []

import urllib.request, urllib.error

mk = os.getenv("MINIMAX_API_KEY", "")
if mk:
    try:
        req = urllib.request.Request(
            "https://api.minimax.chat/v1/text/chatcompletion_v2",
            data=json.dumps({"model":"abab6.5s-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":10}).encode(),
            headers={"Content-Type":"application/json","Authorization":f"Bearer {mk}"})
        resp = urllib.request.urlopen(req, timeout=20)
        d = json.loads(resp.read().decode())
        sc = d.get("base_resp",{}).get("status_code", -1)
        check(f"Minimax API: code={sc}", sc == 0)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        check(f"Minimax HTTP {e.code}: {body}", False)
    except Exception as e:
        check(f"Minimax: {e}", False)
else:
    check("Minimax probe", "MINIMAX_API_KEY not set")

dk = os.getenv("DEEPSEEK_API_KEY", "")
if dk:
    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps({"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":10}).encode(),
            headers={"Content-Type":"application/json","Authorization":f"Bearer {dk}"})
        resp = urllib.request.urlopen(req, timeout=20)
        d = json.loads(resp.read().decode())
        c = d["choices"][0]["message"]["content"][:50]
        check(f"DeepSeek API: '{c}'", True)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        check(f"DeepSeek HTTP {e.code}: {body}", False)
    except Exception as e:
        check(f"DeepSeek: {e}", False)
else:
    check("DeepSeek probe", "DEEPSEEK_API_KEY not set")

try:
    req = urllib.request.Request("http://localhost:11434/api/tags")
    resp = urllib.request.urlopen(req, timeout=5)
    d = json.loads(resp.read().decode())
    models = [m["name"] for m in d.get("models",[])]
    check(f"Ollama: {len(models)} models", True)
except Exception as e:
    check(f"Ollama: {str(e)[:60]}", "not running")

# === TEST 6: heartbeat bilibili ===
print()
print("=" * 50)
print("TEST 6: heartbeat bilibili await")
try:
    with open(os.path.join(NEXUS, "heartbeat_loop.py"), "rb") as f:
        hb = f.read()
    assert b"results = await self.agent.bilibili" in hb
    check("bilibili uses await", True)
except Exception as e:
    check(f"await check: {e}", False)

try:
    idx = hb.find(b'"bilibili", _bilibili()')
    seg = hb[idx:idx+80]
    assert b"timeout=120.0" in seg
    check("bilibili timeout=120.0", True)
except Exception as e:
    check(f"timeout check: {e}", False)

# === SUMMARY ===
print()
print("=" * 50)
print(f"TOTAL: {passed} PASS, {failed} FAIL, {skipped} SKIP")
print("=" * 50)
