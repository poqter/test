import unittest
from streamlit.testing.v1 import AppTest
from modules.finance_calculator_ui import NAMES,MODES

class FinanceUI(unittest.TestCase):
    def app(self,name):
        return AppTest.from_string(f'from modules.finance_calculator_ui import run\nrun({name!r})',default_timeout=20).run()

    def assert_calculated(self,at):
        self.assertFalse(at.exception,[str(x.value) for x in at.exception])
        at.button[0].click().run()
        self.assertFalse(at.exception,[str(x.value) for x in at.exception])
        self.assertGreater(len(at.metric),0)
        self.assertEqual([x.label for x in at.tabs],['고객용 결과','설계사용 상세 계산'])
        self.assertEqual(len(at.get('download_button')),2)

    def test_nine_calculators_and_branches(self):
        for name in NAMES:
            with self.subTest(name=name):
                at=self.app(name)
                self.assert_calculated(at)
                if name in ('수익률계산기','재무계산기','투자수익계산기'):
                    for mode in list(MODES)[1:]:
                        at.selectbox[0].select(mode).run()
                        self.assert_calculated(at)
                if name=='현재가치계산기':
                    at.radio[0].set_value('매년 정기 입금').run()
                    self.assert_calculated(at)

    def test_changed_inputs_replace_results(self):
        at=self.app('미래가치계산기');self.assert_calculated(at)
        first=at.metric[0].value
        at.number_input[0].set_value(20000000)
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertNotEqual(at.metric[0].value,first)

if __name__=='__main__':unittest.main()
