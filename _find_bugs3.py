"""Search for datetime used as parameter name or local variable name."""
import os, re

BASE = r"C:\Users\87999\.nexus"

for root, dirs, files in os.walk(BASE):
    if '__pycache__' in root:
        continue
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            continue
        
        # Search: function parameter named datetime
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # param pattern: def foo(..., datetime, ...) or def foo(..., datetime=..., ...) or def foo(..., datetime:..., ...)
            if re.search(r'def\s+\w+\s*\([^)]*\bdatetime\b', stripped):
                short = fpath.replace(BASE + '\\', '')
                print(f"PARAM: {short}:{i}: {stripped[:120]}")
            
            # local variable named datetime (assignment)
            if re.search(r'\bdatetime\s*=', stripped) and 'import' not in stripped and 'datetime.' not in stripped:
                short = fpath.replace(BASE + '\\', '')
                print(f"ASSIGN: {short}:{i}: {stripped[:120]}")
            
            # for loop variable
            if re.search(r'for\s+datetime\s+in\b', stripped):
                short = fpath.replace(BASE + '\\', '')
                print(f"FOR-LOOP: {short}:{i}: {stripped[:120]}")

            # with statement
            if re.search(r'\bwith\b.*\bas\s+datetime\b', stripped):
                short = fpath.replace(BASE + '\\', '')
                print(f"WITH: {short}:{i}: {stripped[:120]}")
            
            # exception
            if re.search(r'\bexcept\b.*\bas\s+datetime\b', stripped):
                short = fpath.replace(BASE + '\\', '')
                print(f"EXCEPT: {short}:{i}: {stripped[:120]}")
