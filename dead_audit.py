# -*- coding: utf-8 -*-
"""Comprehensive dead reference & dead code audit across all Nexus modules"""
import os, re, ast

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
all_dead_refs = []
all_dead_code = []

for root, dirs, files in os.walk(NEXUS):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if not f.endswith(".py"):
            continue
        fpath = os.path.join(root, f)
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except:
            continue
        
        rel = os.path.relpath(fpath, NEXUS)
        
        # Find all function/method definitions
        defined = set()
        for m in re.finditer(r'(?:async\s+)?def\s+(\w+)\s*\(', content):
            defined.add(m.group(1))
        
        # Find all function calls (identifier followed by parenthesis)
        # Filter out common builtins, keywords, etc.
        builtins = {'print','len','range','int','str','float','bool','list','dict','set',
                     'tuple','type','isinstance','hasattr','getattr','setattr','delattr',
                     'super','enumerate','zip','map','filter','sorted','reversed','min','max',
                     'sum','abs','round','any','all','open','input','next','iter','id',
                     'vars','dir','help','chr','ord','hex','oct','bin','repr','ascii',
                     'format','eval','exec','compile','globals','locals','__import__',
                     'True','False','None','self','cls','Exception','ValueError','TypeError',
                     'logger','time','json','os','sys','Path','datetime','subprocess',
                     'threading','asyncio','random','hashlib','uuid','logging','traceback'}
        
        calls = set()
        for m in re.finditer(r'(?<![.\"\'])\b([a-zA-Z_]\w*)\s*\(', content):
            fn = m.group(1)
            if fn not in builtins and not fn[0].isupper():  # skip ClassNames
                calls.add(fn)
        
        # Dead references: called but not defined in this file
        # (These might be defined in imported modules, so we need to filter)
        local_dead = calls - defined
        
        # Only flag patterns that are clearly problematic:
        # Functions starting with _ that are called but not defined locally
        # These are likely dead references if not imported
        suspicious = {c for c in local_dead if c.startswith('_run_') or c.startswith('_init_') or c.startswith('_start_')}
        
        if suspicious:
            for fn in sorted(suspicious):
                # Count occurrences
                count = len(re.findall(rf'\b{fn}\s*\(', content))
                all_dead_refs.append((rel, fn, count))
        
        # Dead code: functions defined but never called (in this file)
        # Filter out __init__, class methods, etc.
        for fn in sorted(defined):
            if fn.startswith('__') and fn.endswith('__'):
                continue
            # Count calls of this function in the file
            # Exclude the definition line itself
            call_count = len(re.findall(rf'(?<!def\s)(?<!async\sdef\s)\b{fn}\s*\(', content))
            if call_count == 0:
                all_dead_code.append((rel, fn, "defined but never called in file"))

# Print results
print("=" * 60)
print("DEAD REFERENCES (called but never defined)")
print("=" * 60)
for rel, fn, count in all_dead_refs:
    print(f"  {rel}: {fn}() called {count}x")

print()
print("=" * 60)
print("DEAD CODE (defined but never called)")
print("=" * 60)
# Filter: show only interesting ones (_run_, _init_, _start_)
for rel, fn, reason in all_dead_code:
    if fn.startswith('_'):
        print(f"  {rel}: {fn}() — {reason}")

print()
print(f"Total dead refs: {len(all_dead_refs)}")
print(f"Total dead code: {len(all_dead_code)}")
