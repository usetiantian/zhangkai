"""Search for UnboundLocalError patterns in nexus_agent."""
import os
import re

BASE = r"C:\Users\87999\.nexus\nexus_agent"

def find_unbound_local(directory, var_name):
    """Find files where a top-level import is shadowed by a local assignment/import in a nested function."""
    results = []
    for root, dirs, files in os.walk(directory):
        if '__pycache__' in root:
            continue
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    lines = content.split('\n')
            except:
                continue
            
            # Check if file has top-level import of var_name
            has_top_import = bool(re.search(
                rf'^(?:from\s+\S+\s+import\s+.*\b{var_name}\b|import\s+{var_name}\b)',
                content, re.MULTILINE
            ))
            
            if not has_top_import:
                # Check for 'from' import patterns too
                has_top_import = bool(re.search(
                    rf'^import\s+.*\bas\s+{var_name}\b',
                    content, re.MULTILINE
                ))
            
            if not has_top_import:
                continue
            
            # Find all 'import {var_name}' or 'from ... import ... {var_name}' inside function bodies
            # These shadow the top-level import in Python 3.12
            in_function = False
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if re.match(r'^\s*(async\s+)?def\s+\w+', line):
                    in_function = True
                    func_indent = len(line) - len(line.lstrip())
                    continue
                if in_function and stripped and len(line) - len(line.lstrip()) <= func_indent:
                    in_function = False
                    continue
                
                if in_function:
                    # Check for import/reimport that shadows
                    if re.search(rf'(?:import\s+{var_name}\b|from\s+\S+\s+import\s+.*\b{var_name}\b)', line):
                        results.append((fpath.replace(BASE+'\\', ''), i, line.strip(), var_name))
                    # Also check for assignment
                    elif re.search(rf'\b{var_name}\s*=', line) and f'{var_name}.' not in line:
                        results.append((fpath.replace(BASE+'\\', ''), i, line.strip(), f'{var_name} (assignment)'))
    
    return results

# Search for datetime
print("=" * 60)
print("SEARCHING FOR 'datetime' SHADOWING")
print("=" * 60)
for fpath, lineno, line, vtype in find_unbound_local(BASE, 'datetime'):
    print(f"  {fpath}:{lineno} [{vtype}] {line}")

print()
print("=" * 60)
print("SEARCHING FOR 'asyncio' SHADOWING")
print("=" * 60)
for fpath, lineno, line, vtype in find_unbound_local(BASE, 'asyncio'):
    print(f"  {fpath}:{lineno} [{vtype}] {line}")

# Also check nexus_gateway
print()
print("=" * 60)
print("SEARCHING nexus_gateway FOR 'datetime' SHADOWING")
print("=" * 60)
GATEWAY = r"C:\Users\87999\.nexus\nexus_gateway"
for fpath, lineno, line, vtype in find_unbound_local(GATEWAY, 'datetime'):
    print(f"  {fpath}:{lineno} [{vtype}] {line}")

print()
print("SEARCHING nexus_gateway FOR 'asyncio' SHADOWING")  
print("=" * 60)
for fpath, lineno, line, vtype in find_unbound_local(GATEWAY, 'asyncio'):
    print(f"  {fpath}:{lineno} [{vtype}] {line}")
