# -*- coding: utf-8 -*-
"""Fix ScenarioGen — LLM fallback when brain unavailable."""
SRC = r"C:\Users\87999\.nexus\nexus_agent\scenario_generator.py"
f = open(SRC, 'r', encoding='utf-8')
lines = f.readlines()
f.close()

for i, line in enumerate(lines):
    if 'if not self.brain or not self.brain.is_loaded:' in line:
        indent = line[:len(line) - len(line.lstrip())]
        # Replace 'return None' with LLM fallback
        lines[i] = f'{indent}if not self.brain or not self.brain.is_loaded:\n'
        lines.insert(i+1, f'{indent}    pass  # v20: fall through to LLM fallback\n')
        # Now find 'response = self.brain._generate' and wrap with brain check
        for j in range(i+2, min(i+20, len(lines))):
            if 'self.brain._generate' in lines[j]:
                old_line = lines[j]
                new_line = f'{indent}    if self.brain and self.brain.is_loaded:\n'
                new_line += f'{indent}        response = self.brain._generate(full_prompt, max_tokens=500, temperature=0.8)\n'
                new_line += f'{indent}    else:\n'
                new_line += f'{indent}        try:\n'
                new_line += f'{indent}            from nexus_agent.nexus_llm import NexusLLM\n'
                new_line += f'{indent}            llm = NexusLLM()\n'
                new_line += f'{indent}            response = llm.chat([{{\"role\":\"user\",\"content\":full_prompt}}], max_tokens=500)\n'
                new_line += f'{indent}        except Exception:\n'
                new_line += f'{indent}            response = None\n'
                lines[j] = new_line
                print(f'LLM fallback added at L{j+1}')
                break
        break

f = open(SRC, 'w', encoding='utf-8')
f.writelines(lines)
f.close()

import py_compile
py_compile.compile(SRC, doraise=True)
print('[OK]')
