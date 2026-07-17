"""Deep search for UnboundLocalError patterns by checking actual function scope."""
import os, re, ast

BASE = r"C:\Users\87999\.nexus"

def check_file(fpath):
    results = []
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
    except:
        return results
    
    # Find all function definitions with their line ranges
    lines = source.split('\n')
    
    # Find functions that have both a usage of var.XXX and a later import/assignment of var
    in_func = False
    func_start = 0
    func_depth = 0
    var_usage_in_func = {}  # {var_name: first_usage_line}
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Track function scope
        if re.match(r'^\s*(async\s+)?def\s+\w+', line):
            if not in_func:
                in_func = True
                func_start = i
                var_usage_in_func = {}
            func_depth += 1
            continue
        
        if not in_func:
            continue
        
        # Check dedent (end of function)
        indent = len(line) - len(line.lstrip())
        if stripped and indent == 0 and func_depth == 1:
            in_func = False
            func_depth = 0
            continue
        
        # Track base indent for nested defs
        if re.match(r'^\s*(async\s+)?def\s+\w+', line):
            func_depth += 1
            continue
        
        if func_depth != 1:
            continue
        
        # Check for usage of key modules BEFORE import/assignment
        for var in ['datetime', 'asyncio']:
            # Usage pattern: var.xxx (but not import var or from var)
            if re.search(rf'\b{var}\.\w+', line) and f'import {var}' not in line and f'from {var}' not in line:
                if var not in var_usage_in_func:
                    var_usage_in_func[var] = i
            
            # Import that shadows: import var OR from...import...var
            if re.search(rf'(?:^\s*import\s+{var}\b|^\s*from\s+\S+\s+import\s+.*\b{var}\b)', line):
                if var in var_usage_in_func and var_usage_in_func[var] < i:
                    results.append((fpath, var_usage_in_func[var], i, f'{var} used at line {var_usage_in_func[var]}, shadowed by import at line {i}'))
            
            # Assignment that shadows
            if re.search(rf'\b{var}\s*=', line) and f'{var}.' not in line and f'import {var}' not in line:
                if var in var_usage_in_func and var_usage_in_func[var] < i:
                    results.append((fpath, var_usage_in_func[var], i, f'{var} used at line {var_usage_in_func[var]}, shadowed by assignment at line {i}'))
    
    return results

print("SEARCHING FOR SHADOWED MODULE VARIABLES...")
print()

all_results = []
for root, dirs, files in os.walk(BASE):
    if '__pycache__' in root:
        continue
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        results = check_file(fpath)
        for r in results:
            short = fpath.replace(BASE + '\\', '')
            print(f"  {short}:{r[1]} -> {r[2]}: {r[3]}")
            all_results.append(r)

print()
print(f"Total violations found: {len(all_results)}")
