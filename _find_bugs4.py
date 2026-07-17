"""Deep search v3: also catch non-dotted module references like isinstance(x, datetime)."""
import os, re

BASE = r"C:\Users\87999\.nexus"

def check_file(fpath):
    results = []
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except:
        return results
    
    # Track function scope by indentation
    in_func = False
    func_start = 0
    func_base_indent = 0
    func_body_start = 0
    var_first_use = {}
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        
        if not stripped:
            continue
        
        # Detect function start
        if re.match(r'^\s*(async\s+)?def\s+\w+', line):
            if not in_func:
                in_func = True
                func_start = i
                func_base_indent = indent
                func_body_start = i + 1
                var_first_use = {}
            continue
        
        if not in_func:
            continue
        
        # Detect function end (back to base indent or less)
        if indent <= func_base_indent:
            in_func = False
            continue
        
        # Skip nested functions
        if re.match(r'^\s*(async\s+)?def\s+\w+', line):
            continue
        
        # Now in function body (not nested def)
        for var in ['datetime', 'asyncio']:
            # REFERENCE: any use of the module name (dotted or not)
            has_reference = bool(re.search(rf'(?<![.a-zA-Z_]){var}(?:\.[a-zA-Z_]|[^.]\s|\s*$|[,)\]:])', stripped))
            
            # Exclude import lines from being "references"
            if f'import {var}' in stripped or f'from {var}' in stripped:
                has_reference = False
            
            if has_reference and var not in var_first_use:
                var_first_use[var] = i
            
            # SHADOW: import or assignment
            is_import = bool(re.search(rf'(?:import\s+{var}\b|from\s+\S+\s+import\s+.*\b{var}\b)', stripped))
            is_assignment = bool(re.search(rf'\b{var}\s*=', stripped))
            
            if (is_import or is_assignment) and var in var_first_use and var_first_use[var] < i:
                results.append((fpath, var, var_first_use[var], i, stripped[:120]))
                if var in var_first_use:
                    del var_first_use[var]  # report once per var per function
    
    return results

print("DEEP SEARCH v3: Catching isinstance(x, datetime) patterns")
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
        for r in check_file(fpath):
            short = fpath.replace(BASE + '\\', '')
            print(f"  {short}:{r[2]}(use) -> {r[3]}(shadow): [{r[1]}] {r[4]}")
            all_results.append(r)

print()
print(f"Total violations: {len(all_results)}")
if len(all_results) == 0:
    print("No violations found with this method either.")
    print("The error might be in a dynamically evaluated string or exec.")
