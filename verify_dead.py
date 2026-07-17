# -*- coding: utf-8 -*-
"""Verify 6 DEAD _init_* modules — are they really dead or alive via other paths?"""
import sys, os, re

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
sys.path.insert(0, NEXUS)
sys.path.insert(0, os.path.dirname(NEXUS))

def count_refs(pattern, exclude_agent_init=True):
    """Count files referencing a pattern"""
    found = []
    for root, dirs, files in os.walk(NEXUS):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"):
                continue
            if exclude_agent_init and "agent_init" in f:
                continue
            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                if pattern in content:
                    rel = os.path.relpath(fpath, NEXUS)
                    found.append(rel)
            except:
                pass
    return found

checks = [
    ("_init_llm", "NexusLLMClient", "get_llm_client", "llm_client"),
    ("_init_tools", "get_tools_registry", "get_tools_registry", "tools_registry"),
    ("_init_internalizer", "get_internalizer", "get_internalizer", "knowledge_internalizer"),
    ("_init_immune", "get_immune", "get_immune", "nexus_immune"),
    ("_init_bilibili", "get_bilibili_pipeline", "get_bilibili_pipeline", "autonomous/bilibili_pipeline"),
    ("_init_idle_learning", "IdleLearningTimer", "IdleLearningTimer", "idle_learning"),
]

for init_fn, class_name, getter, mod_path in checks:
    print(f"=== {init_fn} ===")
    
    # 1. Is module importable?
    try:
        mod = __import__(f"nexus_agent.{mod_path.replace('/', '.')}", fromlist=[class_name])
        print(f"  Module: OK")
    except ImportError as e:
        print(f"  Module: FAILED ({e})")
    
    # 2. Is the class/getter there?
    if hasattr(mod, class_name):
        print(f"  {class_name}: EXISTS in module")
    elif hasattr(mod, getter):
        print(f"  {getter}: EXISTS in module")
    else:
        print(f"  {class_name}/{getter}: NOT in module")
    
    # 3. References outside agent_init.py?
    refs = count_refs(getter)
    class_refs = count_refs(class_name)
    
    if refs:
        print(f"  {getter}() called from: {refs[:5]}")
        print(f"  VERDICT: ALIVE via lazy singleton")
    elif class_refs:
        print(f"  {class_name} referenced from: {class_refs[:5]}")
        print(f"  VERDICT: ALIVE via direct class usage")
    else:
        print(f"  {getter}/{class_name}: ZERO external references")
        print(f"  VERDICT: TRULY DEAD — only agent_init.py knows about it")
    print()
