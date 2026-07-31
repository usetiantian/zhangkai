"""Evidence-driven source and event attention."""
from dataclasses import dataclass
@dataclass(frozen=True)
class AttentionWeights:
 relevance:float;stability:float;traceability:float;verifiability:float
 def __post_init__(self):
  values=(self.relevance,self.stability,self.traceability,self.verifiability)
  if any(not 0<=x<=1 for x in values) or sum(values)==0:raise ValueError("valid external weights required")
@dataclass(frozen=True)
class SourceCandidate:
 id:str;relevance:float;stability:float;traceability:float;verifiability:float

def attention_score(relevance,stability,traceability,verifiability,weights):
 total=weights.relevance+weights.stability+weights.traceability+weights.verifiability
 return (relevance*weights.relevance+stability*weights.stability+traceability*weights.traceability+verifiability*weights.verifiability)/total
class SourceSelector:
 def __init__(self,weights:AttentionWeights):self.weights=weights
 def rank(self,candidates):return sorted(candidates,key=lambda c:(-attention_score(c.relevance,c.stability,c.traceability,c.verifiability,self.weights),c.id))
