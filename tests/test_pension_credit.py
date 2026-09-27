import unittest
from modules.pension_credit import incremental_credit
class CreditTests(unittest.TestCase):
 def test_existing_and_allocation(self):
  self.assertEqual(incremental_credit(50000000,0,0,300000,3600000),594000)
  self.assertEqual(incremental_credit(60000000,0,0,300000,3600000),475200)
  self.assertEqual(incremental_credit(50000000,6000000,3000000,300000,3600000),0)
  self.assertEqual(incremental_credit(50000000,6000000,0,250000,0),495000)
  with self.assertRaises(ValueError):incremental_credit(50000000,18000000,0,1,0)
 def test_integrated_ui(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string('from modules.pension_calculator_ui import run\nrun()').run()
  at.checkbox[3].check().run();at.button[0].click().run()
  self.assertFalse(at.exception)
  self.assertIn('475,200원',[x.value for x in at.metric])
  self.assertEqual(len(at.get('download_button')),2)
