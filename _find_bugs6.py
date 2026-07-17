"""Search for ANY line where 'datetime' appears on the left side of an assignment or as a bare import inside a function."""
import os, re

BASE = r"C:\Users\87999\.nexus"

for root, dirs, files in os.walk(BASE):
    if '__pycache__' in root or '.git' in root:
        continue
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            continue
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            
            # Pattern: var = ...  where var is exactly 'datetime' or 'asyncio'
            m = re.match(r'^(\s*)(datetime|asyncio)\s*=\s*', line)
            if m:
                short = fpath.replace(BASE + '\\', '')
                print(f"ASSIGN: {short}:{i}: {stripped[:120]}")
            
            # Pattern: for var in ...
            m = re.match(r'^\s*for\s+(datetime|asyncio)\s+in\s+', line)
            if m:
                short = fpath.replace(BASE + '\\', '')
                print(f"FOR: {short}:{i}: {stripped[:120]}")
            
            # Pattern: with ... as var:  
            m = re.match(r'^\s*with\s+.*\bas\s+(datetime|asyncio)\b', line)
            if m:
                short = fpath.replace(BASE + '\\', '')
                print(f"WITH: {short}:{i}: {stripped[:120]}")
            
            # Pattern: except ... as var:
            m = re.match(r'^\s*except\s+.*\bas\s+(datetime|asyncio)\b', line)
            if m:
                short = fpath.replace(BASE + '\\', '')
                print(f"EXCEPT: {short}:{i}: {stripped[:120]}")
            
            # Pattern: in import list: from x import (..., datetime, ...)
            # Already handled by the function-level search
            
            # SPECIAL: inside a string? Check for f-string interpolation
            # or exec/eval with datetime
print()
print("--- Also checking all lines with bare 'datetime' keyword (not datetime., not import, not from) ---")
for root, dirs, files in os.walk(BASE):
    if '__pycache__' in root or '.git' in root:
        continue
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            continue
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            
            # Lines containing 'datetime' but NOT datetime.xxx, NOT import datetime, NOT from datetime
            if re.search(r'\bdatetime\b', stripped):
                if not re.search(r'datetime\.', stripped):
                    if 'import datetime' not in stripped and 'from datetime' not in stripped:
                        # Check: is this line inside a function? (simple check: not at root level)
                        indent = len(line) - len(line.lstrip())
                        if indent >= 4:  # likely inside a function/method
                            short = fpath.replace(BASE + '\\', '')
                            print(f"  {short}:{i}: {stripped[:150]}")
