"""Prediction/outcome learning backed by durable evidence."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PredictionOutcome:
 prediction_id:str
 strategy:str
 expected:str
 actual:str|None
 @property
 def matched(self)->bool:return self.actual is not None and self.expected==self.actual

@dataclass(frozen=True)
class StrategyExperience:
 strategy:str
 samples:int
 successes:int
 success_rate:float

class LearningStore:
 def __init__(self,database:Path):
  self.database=database;database.parent.mkdir(parents=True,exist_ok=True)
  with closing(sqlite3.connect(database)) as c,c:
   c.execute("CREATE TABLE IF NOT EXISTS outcomes(prediction_id TEXT PRIMARY KEY,strategy TEXT NOT NULL,expected TEXT NOT NULL,actual TEXT)")
 def predict(self,prediction_id:str,strategy:str,expected:str)->None:
  if not all(x.strip() for x in (prediction_id,strategy,expected)):raise ValueError("prediction fields required")
  with closing(sqlite3.connect(self.database)) as c,c:c.execute("INSERT INTO outcomes VALUES(?,?,?,NULL)",(prediction_id,strategy,expected))
 def observe(self,prediction_id:str,actual:str)->None:
  if not actual.strip():raise ValueError("actual outcome required")
  with closing(sqlite3.connect(self.database)) as c,c:
   cur=c.execute("UPDATE outcomes SET actual=? WHERE prediction_id=? AND actual IS NULL",(actual,prediction_id))
   if cur.rowcount!=1:raise KeyError(prediction_id)
 def get(self,prediction_id:str)->PredictionOutcome:
  with closing(sqlite3.connect(self.database)) as c:row=c.execute("SELECT prediction_id,strategy,expected,actual FROM outcomes WHERE prediction_id=?",(prediction_id,)).fetchone()
  if not row:raise KeyError(prediction_id)
  return PredictionOutcome(*row)
 def strategy_stats(self)->list[StrategyExperience]:
  with closing(sqlite3.connect(self.database)) as c:rows=c.execute("SELECT strategy,COUNT(*),SUM(CASE WHEN actual='success' THEN 1 ELSE 0 END) FROM outcomes WHERE actual IS NOT NULL GROUP BY strategy").fetchall()
  return [StrategyExperience(strategy,count,successes,successes/count) for strategy,count,successes in rows]

class StrategyLearner:
 def __init__(self,store:LearningStore,*,min_samples:int):
  if min_samples<1:raise ValueError("min_samples must be supplied and positive")
  self.store=store;self.min_samples=min_samples
 def _eligible(self)->list[StrategyExperience]:
  return [x for x in self.store.strategy_stats() if x.samples>=self.min_samples]
 def best(self)->StrategyExperience|None:
  eligible=self._eligible()
  return max(eligible,key=lambda x:(x.success_rate,x.samples,x.strategy)) if eligible else None
 def improvement_over(self,baseline:str)->float|None:
  eligible={x.strategy:x for x in self._eligible()}
  best=self.best()
  return None if best is None or baseline not in eligible else best.success_rate-eligible[baseline].success_rate
