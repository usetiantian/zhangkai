import json,tempfile,unittest
from pathlib import Path
from config.loader import ConfigError,load_config

VALID={
 "identity":{"name":"shui","version":"1","mission":["learn","verify"]},
 "values":[{"name":"truth","weight":1.0,"source":"owner-decision","calibrated_at":"2026-07-31T00:00:00+00:00"}],
 "sources":[{"id":"python-tags","url":"https://api.github.com/repos/python/cpython/tags?per_page=1"}],
 "schedules":{"fast_seconds":60,"slow_seconds":3600},
 "capabilities":{"enabled":["observe.http","write.verified-report"]},
 "paths":{"state":"../state","actions":"../actions","audit":"../audit/events.jsonl"},
 "runtime":{"http_timeout_seconds":10,"capability_timeout_seconds":10,"learning_min_samples":2}
}
class ConfigTests(unittest.TestCase):
 def write(self,root,data):
  path=root/"config"/"shui.json";path.parent.mkdir();path.write_text(json.dumps(data));return path
 def test_complete_config_loads_and_paths_resolve_from_config_file(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);config=load_config(self.write(root,VALID))
   self.assertEqual(config.identity.name,"shui")
   self.assertEqual(config.paths.state,(root/"state").resolve())
   self.assertEqual(config.schedules.fast_seconds,60)
 def test_missing_required_section_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   data=dict(VALID);data.pop("values")
   with self.assertRaisesRegex(ConfigError,"values"):load_config(self.write(Path(d),data))
 def test_unknown_field_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   data=dict(VALID);data["invented"]={}
   with self.assertRaisesRegex(ConfigError,"invented"):load_config(self.write(Path(d),data))
 def test_secret_like_fields_are_rejected_at_any_depth(self):
  with tempfile.TemporaryDirectory() as d:
   data=json.loads(json.dumps(VALID));data["runtime"]["github_token"]="exposed"
   with self.assertRaisesRegex(ConfigError,"github_token"):load_config(self.write(Path(d),data))
 def test_invalid_weight_and_schedule_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   data=json.loads(json.dumps(VALID));data["values"][0]["weight"]=2
   with self.assertRaises(ConfigError):load_config(self.write(Path(d),data))
  with tempfile.TemporaryDirectory() as d:
   data=json.loads(json.dumps(VALID));data["schedules"]["fast_seconds"]=0
   with self.assertRaises(ConfigError):load_config(self.write(Path(d),data))

if __name__=="__main__":unittest.main()
