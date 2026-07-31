"""Versioned capability construction, isolated evaluation and rollback."""
from __future__ import annotations
import ast,json,shutil,subprocess,sys
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class CapabilitySpec:
 id:str; input_kind:str; output_kind:str
@dataclass(frozen=True)
class CapabilityDraft:
 spec:CapabilitySpec; test_input:str; expected:str
@dataclass(frozen=True)
class Candidate:
 spec:CapabilitySpec; version:str; path:Path
@dataclass(frozen=True)
class Evaluation:
 passed:bool; actual:str|None; error:str|None

class CapabilityEvolution:
 def __init__(self,root:Path):
  self.root=root;self.candidates=root/"candidates";self.stable=root/"stable";self.registry=root/"registry.json"
  self.candidates.mkdir(parents=True,exist_ok=True);self.stable.mkdir(exist_ok=True)
  if not self.registry.exists():self.registry.write_text("{}",encoding="utf-8")
 def discover_gap(self,capability_id:str,test_input:str,expected:str)->CapabilityDraft:
  if not all((capability_id.strip(),test_input,expected)):raise ValueError("gap evidence required")
  return CapabilityDraft(CapabilitySpec(capability_id,"text","text"),test_input,expected)
 def build(self,draft:CapabilityDraft,version:str,source:str)->Candidate:
  tree=ast.parse(source)
  if any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree)):raise ValueError("candidate imports are not allowed")
  if not any(isinstance(n,ast.FunctionDef) and n.name=="execute" for n in tree.body):raise ValueError("execute function required")
  path=self.candidates/f"{draft.spec.id.replace('.','_')}-{version}.py";path.write_text(source,encoding="utf-8")
  return Candidate(draft.spec,version,path)
 def _run(self,path:Path,value:str)->Evaluation:
  script="import json,runpy,sys;m=runpy.run_path(sys.argv[1]);print(json.dumps(m['execute'](json.loads(sys.argv[2]))))"
  result=subprocess.run([sys.executable,"-I","-c",script,str(path),json.dumps(value)],capture_output=True,text=True,timeout=10)
  if result.returncode:return Evaluation(False,None,result.stderr.strip())
  try:return Evaluation(True,json.loads(result.stdout),None)
  except Exception as error:return Evaluation(False,None,str(error))
 def evaluate(self,candidate:Candidate,draft:CapabilityDraft)->Evaluation:
  result=self._run(candidate.path,draft.test_input)
  return Evaluation(result.passed and result.actual==draft.expected,result.actual,result.error)
 def _load(self)->dict:return json.loads(self.registry.read_text(encoding="utf-8"))
 def _save(self,data:dict)->None:self.registry.write_text(json.dumps(data,indent=2,sort_keys=True),encoding="utf-8")
 def promote(self,candidate:Candidate,result:Evaluation)->None:
  if not result.passed:raise ValueError("candidate did not pass")
  destination=self.stable/candidate.path.name;shutil.copy2(candidate.path,destination)
  data=self._load();entry=data.setdefault(candidate.spec.id,{"versions":[],"current":None});entry["versions"].append({"version":candidate.version,"path":str(destination)});entry["current"]=len(entry["versions"])-1;self._save(data)
 def is_registered(self,capability_id:str)->bool:return capability_id in self._load()
 def execute(self,capability_id:str,value:str)->str:
  entry=self._load().get(capability_id)
  if not entry:raise KeyError(capability_id)
  result=self._run(Path(entry["versions"][entry["current"]]["path"]),value)
  if not result.passed:raise RuntimeError(result.error)
  return result.actual
 def rollback(self,capability_id:str)->None:
  data=self._load();entry=data.get(capability_id)
  if not entry or entry["current"]<1:raise ValueError("no previous stable version")
  entry["current"]-=1;self._save(data)
