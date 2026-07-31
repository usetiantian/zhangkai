import tempfile, unittest
from pathlib import Path
from evolution.engine import CapabilityEvolution, CapabilitySpec

GOOD='def execute(value):\n    return value.upper()\n'
BAD='def execute(value):\n    return value.lower()\n'

class CapabilityEvolutionTests(unittest.TestCase):
 def test_missing_capability_creates_spec_and_test_draft(self):
  with tempfile.TemporaryDirectory() as d:
   evo=CapabilityEvolution(Path(d))
   draft=evo.discover_gap("text.upper","abc","ABC")
   self.assertEqual(draft.spec,CapabilitySpec("text.upper","text","text"))
   self.assertEqual(draft.test_input,"abc");self.assertEqual(draft.expected,"ABC")
 def test_candidate_must_pass_isolated_acceptance_test_before_registration(self):
  with tempfile.TemporaryDirectory() as d:
   evo=CapabilityEvolution(Path(d));draft=evo.discover_gap("text.upper","abc","ABC")
   candidate=evo.build(draft,"1",BAD)
   result=evo.evaluate(candidate,draft)
   self.assertFalse(result.passed);self.assertFalse(evo.is_registered("text.upper"))
 def test_verified_capability_registers_and_completes_blocked_goal(self):
  with tempfile.TemporaryDirectory() as d:
   evo=CapabilityEvolution(Path(d));draft=evo.discover_gap("text.upper","abc","ABC")
   candidate=evo.build(draft,"1",GOOD); result=evo.evaluate(candidate,draft)
   self.assertTrue(result.passed);evo.promote(candidate,result)
   self.assertEqual(evo.execute("text.upper","water"),"WATER")
 def test_new_version_can_roll_back_to_previous_stable_version(self):
  with tempfile.TemporaryDirectory() as d:
   evo=CapabilityEvolution(Path(d));draft=evo.discover_gap("text.upper","abc","ABC")
   one=evo.build(draft,"1",GOOD);evo.promote(one,evo.evaluate(one,draft))
   two=evo.build(draft,"2",GOOD.replace('upper()','upper()+"!"'))
   custom=evo.discover_gap("text.upper","abc","ABC!");evo.promote(two,evo.evaluate(two,custom))
   self.assertEqual(evo.execute("text.upper","x"),"X!")
   evo.rollback("text.upper");self.assertEqual(evo.execute("text.upper","x"),"X")

if __name__=="__main__":unittest.main()
