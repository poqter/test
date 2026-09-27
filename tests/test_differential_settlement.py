import unittest
from modules import differential_dividend as d
class Settlement(unittest.TestCase):
 def calc(self,**kw):return d.differential(eligible='예',stage=d.STAGES[1],actual_confirmed='예',**kw).metrics
 def test_comprehensive_increment_and_floor(self):
  # 150m tax35% less 40m tax15% =37.06m -4.74m.
  self.assertEqual(self.calc(settlement=d.SETTLEMENT[1],settlement_base=150000000)['증여재산에서 차감하는 소득세 상당액'],32320000)
  self.assertEqual(self.calc(settlement=d.SETTLEMENT[1],settlement_base=0)['증여재산에서 차감하는 소득세 상당액'],15400000)
 def test_separate_excluded_and_guards(self):
  self.assertEqual(self.calc(settlement=d.SETTLEMENT[2],separate_rate=14)['증여재산에서 차감하는 소득세 상당액'],15400000)
  self.assertEqual(self.calc(settlement=d.SETTLEMENT[3])['증여재산에서 차감하는 소득세 상당액'],0)
  with self.assertRaises(ValueError):self.calc(settlement=d.SETTLEMENT[1],actual=1)
  with self.assertRaises(ValueError):d.differential(settlement=d.SETTLEMENT[1])
