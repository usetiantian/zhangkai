"""One-shot indent fixup for heartbeat_loop.py.
The patch tool's first failed edit left lines 838-870 over-indented by 12 spaces.
This script dedents those lines so the file parses cleanly. Does not modify any logic.
"""
from pathlib import Path

PATH = Path("C:/Users/87999/.nexus/nexus_agent/heartbeat_loop.py")
START_LINE = 838  # 1-indexed, inclusive
END_LINE = 870    # 1-indexed, inclusive
DEDENT = 12       # spaces to remove

text = PATH.read_text(encoding="utf-8")
lines = text.split("\n")

# Convert to 0-indexed
s = START_LINE - 1
e = END_LINE - 1

fixed = 0
for i in range(s, e + 1):
    if i >= len(lines):
        break
    line = lines[i]
    # Count leading whitespace
    stripped = line.lstrip(" ")
    leading = len(line) - len(stripped)
    if leading >= DEDENT:
        new_line = line[DEDENT:]
        if new_line != line:
            lines[i] = new_line
            fixed += 1

PATH.write_text("\n".join(lines), encoding="utf-8")
print(f"Fixed {fixed} lines between {START_LINE} and {END_LINE}")

# Quick sanity: try to import
import subprocess
result = subprocess.run(
    ["python", "-c", "import ast; ast.parse(open(r'C:/Users/87999/.nexus/nexus_agent/heartbeat_loop.py').read())"],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("AST parse: OK")
else:
    print("AST parse FAILED:", result.stderr[:500])