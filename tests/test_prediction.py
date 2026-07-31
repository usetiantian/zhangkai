import json, unittest
from datetime import datetime, timezone
from contracts import Prediction, record_from_dict
class PredictionTests(unittest.TestCase):
 def test_prediction_round_trip(self):
  now=datetime(2026,7,31,tzinfo=timezone.utc)
  item=Prediction(id="pred-1",schema_version="1",created_at=now,action_id="step-1",expected_outcome="file hash changes",verification_condition="observed hash equals expected")
  self.assertEqual(record_from_dict(json.loads(json.dumps(item.to_dict()))),item)
if __name__=="__main__":unittest.main()
