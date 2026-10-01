"""Optional REAL Streamlit boot test; explicitly skipped without Streamlit.

AppTest does not render the custom component browser frontend. Use the separate
component/browser harness for that part, then manually confirm Community Cloud.
"""
import importlib.util
from pathlib import Path
import unittest

@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'NOT RUN: Streamlit runtime is not installed')
class StreamlitEntryTests(unittest.TestCase):
    def test_public_demo_boot(self):
        from streamlit.testing.v1 import AppTest
        target=Path(__file__).resolve().parents[2]/'academy_app.py'
        app=AppTest.from_file(str(target),default_timeout=15)
        app.secrets['academy']={'access_mode':'public_demo'}
        app.run()
        self.assertEqual(len(app.exception),0)
    def test_simulator_route_boot(self):
        from streamlit.testing.v1 import AppTest
        target=Path(__file__).resolve().parents[2]/'academy_app.py'
        app=AppTest.from_file(str(target),default_timeout=15)
        app.secrets['academy']={'access_mode':'public_demo'}
        app.query_params['view']='simulator';app.query_params['scenario']='C07-S01'
        app.run()
        self.assertEqual(len(app.exception),0)

if __name__=='__main__':unittest.main()
