# -*- coding: utf-8 -*-
"""Replace regex triple extraction with Qwen-based structured knowledge extraction."""
import py_compile
SRC = r"C:\Users\87999\.nexus\nexus_agent\knowledge_generator.py"

f = open(SRC, 'r', encoding='utf-8')
content = f.read()
f.close()

# Replace _extract_triples with Qwen-based version
old = '    def _extract_triples(self, text: str, domain: str) -> list:'
old_end = '    def _verb_to_relation(self, verb: str):'

idx_start = content.find(old)
idx_end = content.find(old_end)
if idx_start < 0 or idx_end < 0:
    print('ERROR: markers')
    exit(1)

NL = chr(10)
new_method = f'''    def _extract_triples(self, text: str, domain: str) -> list:
        """v20: Qwen-based structured knowledge extraction.
        Uses local Qwen2-VL-2B to extract entities, relations, and triples.
        Falls back to simple keyword extraction if Qwen unavailable."""
        # Try Qwen first
        triples = self._qwen_extract_triples(text, domain)
        if triples:
            return triples
        # Fallback: simple keyword-based extraction
        return self._simple_extract_triples(text)

    def _qwen_extract_triples(self, text: str, domain: str) -> list:
        """Use local Qwen to extract structured knowledge triples."""
        try:
            from nexus_agent.nexus_brain import get_brain
            brain = get_brain()
            if not brain.is_loaded:
                return []
            prompt = f\"\"\"Extract up to 5 key knowledge triples from this text about {domain}.
Format each as: SUBJECT | PREDICATE | OBJECT
Predicate must be one of: uses, improves, enables, produces, depends_on, contains, reduces, requires

Text: {text[:600]}

Triples:\"\"\"
            response = brain._generate(prompt, max_tokens=200, temperature=0.1)
            if not response: return []
            triples = []
            for line in response.strip().split(chr(10)):
                line = line.strip()
                if '|' not in line: continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    subj, pred, obj = parts[0], parts[1], parts[2]
                    if len(subj) > 2 and len(obj) > 2:
                        triples.append((subj[:80], pred[:30], obj[:80]))
            return triples[:5]
        except Exception:
            return []

    def _simple_extract_triples(self, text: str) -> list:
        """Fallback: simple keyword heuristic when Qwen unavailable."""
        import re
        triples = []
        # Basic: find domain-relevant noun phrases
        concepts = re.findall(r'[A-Z][a-zA-Z]{2,}(?:\\s+[a-zA-Z]{2,}){0,2}', text)
        for i in range(len(concepts)-1):
            if len(concepts[i]) > 3 and len(concepts[i+1]) > 3:
                triples.append((concepts[i][:60], 'relates_to', concepts[i+1][:60]))
        return triples[:5]

    def _verb_to_relation(self, verb: str):'''

content = content[:idx_start] + new_method + content[idx_end:]
f = open(SRC, 'w', encoding='utf-8')
f.write(content)
f.close()

py_compile.compile(SRC, doraise=True)
print('[OK] Qwen-based extraction replaces regex')
