"""Search v4: properly track function scopes with indentation stack."""
import os, re

BASE = r"C:\Users\87999\.nexus"

def check_file_good_scope(fpath):
    """Use a simple but more reliable method: for each function body,
    check if 'import datetime' or 'from datetime import' appears after
    a use of 'datetime' in the same function."""
    results = []
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except:
        return results
    
    # Find function boundaries by tracking indent stack
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if this is a function definition
        m = re.match(r'^(\s*)(?:async\s+)?def\s+(\w+)\s*\(', line)
        if not m:
            i += 1
            continue
        
        base_indent = len(m.group(1))
        func_start = i
        func_name = m.group(2)
        
        # Find end of function (next line with same or less indent, not within nested block)
        i += 1
        while i < len(lines):
            next_line = lines[i]
            next_stripped = next_line.strip()
            if next_stripped and not next_stripped.startswith('#'):
                indent = len(next_line) - len(next_line.lstrip())
                if indent <= base_indent:
                    break
            i += 1
        
        func_end = i
        
        # Check this function body for datetime/asyncio pattern
        for var in ['datetime', 'asyncio']:
            first_use = None
            first_shadow = None
            
            for j in range(func_start + 1, func_end):
                l = lines[j].strip()
                
                # USE: any reference to var.xxx or isinstance(x, var) or just bare var
                if re.search(rf'\b{var}\b', l) and not re.search(rf'(?:import\s+{var}\b|from\s+{var}\b)', l):
                    if first_use is None:
                        first_use = j + 1  # 1-based
                
                # SHADOW: import var or from x import var
                if re.search(rf'(?:^\s*import\s+{var}\b|^\s*from\s+\S+\s+import\s+.*\b{var}\b)', l):
                    if first_shadow is None:
                        first_shadow = j + 1
                
                # ASSIGNMENT shadow: var = 
                if re.search(rf'\b{var}\s*=\s*', l) and f'{var}.' not in l:
                    if first_shadow is None:
                        first_shadow = j + 1
            
            if first_use is not None and first_shadow is not None and first_use < first_shadow:
                short = fpath.replace(BASE + '\\', '')
                use_line = lines[first_use - 1].strip()[:100]
                shadow_line = lines[first_shadow - 1].strip()[:100]
                results.append((short, func_name, var, first_use, first_shadow, use_line, shadow_line))
    
    return results

print("DEEP SEARCH v4: proper function scope tracking")
print()

all_results = []
for root, dirs, files in os.walk(BASE):
    if '__pycache__' in root or '.git' in root:
        continue
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        for r in check_file_good_scope(fpath):
            short, func_name, var, first_use, first_shadow, use_line, shadow_line = r
            print(f"  {short}")
            print(f"    [{var}] {func_name}() — use at line {first_use}, shadow at line {first_shadow}")
            print(f"    USE:    {use_line}")
            print(f"    SHADOW: {shadow_line}")
            print()
            all_results.append(r)

print(f"Total violations: {len(all_results)}")
