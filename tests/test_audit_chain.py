import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from audit.chain import AuditChain,AuditError

NOW=datetime(2026,7,31,tzinfo=timezone.utc)
class AuditChainTests(unittest.TestCase):
 def test_events_append_with_causal_and_hash_chain(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl";chain=AuditChain(path)
   first=chain.append("e1",NOW,"observe.completed",None,"success",{"source":"file"})
   second=chain.append("e2",NOW,"action.verified","e1","success",{"receipt":"r1"})
   self.assertEqual(second.previous_hash,first.event_hash)
   self.assertTrue(chain.verify())
   self.assertEqual(len(path.read_text().splitlines()),2)
 def test_reopened_chain_continues_from_last_hash(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl";first=AuditChain(path).append("e1",NOW,"one",None,"ok",{})
   second=AuditChain(path).append("e2",NOW,"two","e1","ok",{})
   self.assertEqual(second.previous_hash,first.event_hash);self.assertTrue(AuditChain(path).verify())
 def test_tampering_is_detected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.jsonl";AuditChain(path).append("e1",NOW,"one",None,"ok",{"value":1})
   record=json.loads(path.read_text());record["data"]["value"]=2
   path.write_text(json.dumps(record)+"\n")
   self.assertFalse(AuditChain(path).verify())
 def test_sensitive_fields_are_rejected_recursively(self):
  with tempfile.TemporaryDirectory() as d:
   chain=AuditChain(Path(d)/"events.jsonl")
   for data in ({"token":"x"},{"headers":{"Authorization":"Bearer x"}},{"api_key":"x"}):
    with self.assertRaises(AuditError):chain.append("e",NOW,"x",None,"failed",data)
 def test_naive_time_and_duplicate_event_id_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   chain=AuditChain(Path(d)/"events.jsonl")
   with self.assertRaises(AuditError):chain.append("e",datetime(2026,7,31),"x",None,"ok",{})
   chain.append("e",NOW,"x",None,"ok",{})
   with self.assertRaises(AuditError):chain.append("e",NOW,"x",None,"ok",{})

if __name__=="__main__":unittest.main()
