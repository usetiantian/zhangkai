# -*- coding: utf-8 -*-
"""Fix evokg — heuristic rules, no hardcoded patterns."""
SRC = r"C:\Users\87999\.nexus\nexus_agent\evokg.py"
f = open(SRC, 'r', encoding='utf-8')
content = f.read()
f.close()

old = '''        # v20: Quality gate — reject junk before it enters the KG
        if not content or len(str(content)) < 15:
            logger.debug("[EvoKG] add_node rejected: content too short (%d chars)", len(str(content)))
            return None
        junk_patterns = ['stock_team/', '__init__', '.py:', '_init_idle', '_store_fix']
        content_str = str(content)
        if any(p in content_str for p in junk_patterns) and len(content_str) < 200:
            logger.debug("[EvoKG] add_node rejected: junk pattern in content")
            return None
        # Cap confidence — no blind 0.9 without evidence
        confidence = min(0.85, max(0.1, confidence))

        if node_id is None:'''

BS = chr(92)  # backslash
new = f'''        # v20: Quality gate — heuristic rules (no hardcoded filenames)
        content_str = str(content)
        clen = len(content_str)
        if not content or clen < 20:
            return None
        # Looks like a file path? Low alpha ratio + path separators
        alpha_ratio = sum(1 for c in content_str if c.isalpha() or c.isspace()) / max(clen, 1)
        has_path = '/' in content_str or '{BS}' in content_str
        if has_path and alpha_ratio < 0.3 and clen < 200:
            return None
        # High confidence with tiny content = inflated — scale proportionally
        if confidence > 0.7 and clen < 80:
            confidence = 0.4 + 0.3 * (clen / 80.0)
        else:
            confidence = min(0.85, max(0.1, confidence))

        if node_id is None:'''

content = content.replace(old, new)
f = open(SRC, 'w', encoding='utf-8')
f.write(content)
f.close()

import py_compile
py_compile.compile(SRC, doraise=True)
print('[OK] evokg — heuristic rules, no hardcoded filenames')
