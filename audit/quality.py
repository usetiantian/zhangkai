"""Deterministic Python readability checks."""
from __future__ import annotations
import io,tokenize
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class QualityIssue:
 path:Path;line:int;kind:str;detail:str

def scan(root:Path,*,max_length:int=100)->list[QualityIssue]:
 issues=[]
 for path in root.rglob("*.py"):
  if any(part in {".git","tests","__pycache__"} for part in path.parts):continue
  text=path.read_text(encoding="utf-8")
  for number,line in enumerate(text.splitlines(),1):
   if len(line)>max_length:issues.append(QualityIssue(path,number,"long_line",str(len(line))))
  try:tokens=tokenize.generate_tokens(io.StringIO(text).readline)
  except (tokenize.TokenError,IndentationError):continue
  for token in tokens:
   if token.type==tokenize.OP and token.string==";":issues.append(QualityIssue(path,token.start[0],"multiple_statements","semicolon"))
 return issues
