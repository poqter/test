import unittest
from streamlit.testing.v1 import AppTest
class PensionUI(unittest.TestCase):
 def test_center_route(self):
  at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
  at.selectbox(key='jc_selected').select('연금계산기').run()
  at.button[0].click().run();self.assertFalse(at.exception)
  self.assertTrue(at.metric);self.assertEqual(len(at.get('download_button')),2)
  at.number_input(key='pp_age').set_value(70);at.button[0].click().run()
  self.assertFalse(at.exception);self.assertTrue(at.error);self.assertFalse(at.metric)
