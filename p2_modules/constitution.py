# -*- coding: utf-8 -*-
"""Constitution v2.0 — Enforceable AI Constitution (Anthropic CAI + DeepMind Sparrow)"""
import hashlib, re, time, logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class PrincipleCategory(Enum):
    SAFETY="safety"; HONESTY="honesty"; HELPFULNESS="helpfulness"; PRIVACY="privacy"; AUTONOMY="autonomy"

@dataclass(frozen=True)
class Principle:
    id: str; category: PrincipleCategory; statement: str; check_fn_name: str; weight: float=1.0; priority: int=5

@dataclass
class Violation:
    principle_id: str; severity: float; evidence: str; suggestion: str; timestamp: float=field(default_factory=time.time)

@dataclass
class ConstitutionAudit:
    action: str; score: float; violations: List[Violation]; passed: bool=True; timestamp: float=field(default_factory=time.time)

PRINCIPLES = [
    Principle("S1",PrincipleCategory.SAFETY,"No destructive ops without confirmation.","check_destructive",2.0,1),
    Principle("S2",PrincipleCategory.SAFETY,"No irreversible changes without approval.","check_irreversible",2.0,1),
    Principle("S3",PrincipleCategory.SAFETY,"No file access outside workspace.","check_path_traversal",1.5,2),
    Principle("H1",PrincipleCategory.HONESTY,"Never fabricate capabilities.","check_fabrication",1.5,3),
    Principle("H3",PrincipleCategory.HONESTY,"Never hide errors from user.","check_error_hiding",1.5,3),
    Principle("HL1",PrincipleCategory.HELPFULNESS,"Generated code must be valid.","check_code_quality",1.0,6),
    Principle("P1",PrincipleCategory.PRIVACY,"Never expose secrets/tokens.","check_secrets",2.0,1),
    Principle("A1",PrincipleCategory.AUTONOMY,"Self-modification needs review + reversible guard.","check_self_modify",1.5,3),
]

class ConstitutionScorer:
    DESTRUCTIVE=[r'\brm\s+-rf\b',r'\bDROP\s+TABLE\b',r'\bshutil\.rmtree\b',r'\bos\.remove\b',r'\bformat\s+[a-z]:']
    IRREVERSIBLE=[r'\bpip\s+(uninstall|remove)\b',r'\bnpm\s+(uninstall|remove)\b',r'\bapt-get\s+(remove|purge)\b']
    SECRETS=[r'(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*[\x27\x22][^\x27\x22]{8,}',r'(?i)(sk-[a-zA-Z0-9]{20,})',r'(?i)(ghp_[a-zA-Z0-9]{30,})']

    def __init__(self):
        self._history=[]; self._cache={}

    def score(self, action, ctx=None):
        key=hashlib.md5(action.encode()).hexdigest()
        if key in self._cache: return ConstitutionAudit(action=action[:200],score=self._cache[key],violations=[])
        violations=[]; total_w=sum(p.weight for p in PRINCIPLES); ws=0.0
        for p in PRINCIPLES:
            fn=getattr(self,p.check_fn_name,None)
            if fn is None: ws+=p.weight; continue
            sev,ev=fn(action,ctx)
            if sev>0:
                ws+=p.weight*(1.0-sev)
                violations.append(Violation(principle_id=p.id,severity=sev,evidence=ev[:300],suggestion=self._suggest(p.id)))
            else: ws+=p.weight
        score=round(ws/max(total_w,1e-9),4)
        self._cache[key]=score
        if len(self._cache)>500: self._cache.clear()
        self._history.extend(violations)
        if len(self._history)>1000: self._history=self._history[-500:]
        return ConstitutionAudit(action=action[:500],score=score,violations=violations,passed=score>=0.5)

    def check_destructive(self,a,ctx):
        for p in self.DESTRUCTIVE:
            if re.search(p,a): return 0.9,f"destructive:{p}"
        return 0.0,""
    def check_irreversible(self,a,ctx):
        for p in self.IRREVERSIBLE:
            if re.search(p,a): return 0.8,f"irreversible:{p}"
        return 0.0,""
    def check_path_traversal(self,a,ctx):
        for p in [r'\.\./',r'\.\.\\',r'/etc/',r'C:\\Windows']:
            if re.search(p,a): return 0.6,f"path:{p}"
        return 0.0,""
    def check_fabrication(self,a,ctx):
        if re.search(r'I (have|just) (created|built|deployed)',a,re.I) and ctx and not ctx.get("_executed"):
            return 0.7,"unverified claim"
        return 0.0,""
    def check_error_hiding(self,a,ctx):
        if re.search(r'except\s*:\s*pass',a) and 'logger' not in a:
            return 0.5,"silent error suppression"
        return 0.0,""
    def check_code_quality(self,a,ctx):
        n=sum([1 for _ in[1]if 'except:' in a and 'Exception' not in a]+[1 for _ in[1]if a.count('\t')>5])
        return min(n*0.2,0.6),f"{n} quality issues" if n else ""
    def check_secrets(self,a,ctx):
        for p in self.SECRETS:
            if re.search(p,a): return 1.0,f"secret:{p[:60]}"
        return 0.0,""
    def check_self_modify(self,a,ctx):
        if any(k in a for k in['self_modifier','self._','self.modify']):
            if not any(k in a.lower() for k in['review','verify','backup','rollback','git']):
                return 0.5,"self-mod without guard"
        return 0.0,""
    def _suggest(self,pid):
        return {"S1":"Confirm before destructive ops.","S2":"Backup before irreversible changes.","S3":"Restrict to workspace.","H1":"Only claim executed actions.","H3":"Log all errors.","HL1":"Syntax-check before deploy.","P1":"Strip secrets.","A1":"Need review+reversible guard."}.get(pid,"Fix violation.")
    def get_stats(self):
        r=self._history[-100:]
        return {"total":len(self._history),"recent":len(r),"top_violated":sorted(set(v.principle_id for v in r),key=lambda p:sum(1 for v in r if v.principle_id==p),reverse=True)[:5],"avg_severity":round(sum(v.severity for v in r)/max(len(r),1),3)}

_c=None
def get_constitution():
    global _c
    if _c is None: _c=ConstitutionScorer()
    return _c
def score_action(a,ctx=None): return get_constitution().score(a,ctx)
