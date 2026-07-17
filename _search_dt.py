import os
BASE = r"C:\Users\87999\.nexus"
for root, dirs, files in os.walk(BASE):
    if '__pycache__' in root:
        continue
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f, 1):
                    s = line.strip()
                    if 'datetime' in s and '=' in s:
                        if not s.startswith('#') and 'import' not in s and 'from datetime' not in s:
                            if 'timestamp' not in s.lower():
                                short = fpath.replace(BASE+'\\','')
                                print(f"{short}:{i}: {s[:150]}")
        except:
            pass
print("--- done ---")
