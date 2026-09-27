import unittest
from decimal import Decimal as D
from modules import finance_models as m

class FinanceObservedCases(unittest.TestCase):
    """Numerical expectations transcribed from saved visible JARVIA snapshots."""
    def test_future_and_compound(self):
        self.assertEqual(m.future_value().display()['예상 최종 자금'],'39,869,900원')
        self.assertEqual(m.compound().display()['예상 최종 자금'],'16,470,094원')
        self.assertEqual(m.future_value(rate=0).metrics['예상 최종 자금'],D(14000000))

    def test_investment_modes(self):
        common=dict(principal=20000000,payment=200000,target=100000000,years=15,rate=6)
        expected={'future':('예상 최종 자금','107,245,614원'),'payment':('필요 정기 납입액','175,085원'),
                  'rate':('필요 연 수익률','5.39%'),'principal':('필요 시작 자금','17,047,540원'),
                  'period':('필요 납입 횟수','170회')}
        for mode,(key,value) in expected.items():
            with self.subTest(mode=mode):
                r=m.tvm(mode,**common)
                self.assertEqual(r.display()[key],value)
                # Original site's table uses a different rate: our table must use the headline engine.
                self.assertEqual(r.rows[-1]['총 자금'],r.metrics['예상 최종 자금'])
        self.assertEqual(m.investment('future',principal=20000000,monthly=200000,years=15,rate=6,frequency=4).display()['예상 최종 자금'],'106,593,187원')

    def test_general_tvm(self):
        common=dict(principal=10000000,payment=100000,target=30000000,years=10,rate=5)
        for mode,key,value in [('future','예상 최종 자금','31,998,323원'),('payment','필요 정기 납입액','87,131원'),
                               ('rate','필요 연 수익률','4.16%'),('principal','필요 시작 자금','8,786,696원')]:
            self.assertEqual(m.tvm(mode,**common).display()[key],value)
        r=m.tvm('period',**common);n=int(r.metrics['필요 납입 횟수'])
        self.assertGreaterEqual(r.metrics['예상 최종 자금'],D(30000000))
        self.assertLess(m.fv(D(10000000),D(100000),D('.05')/12,n-1),D(30000000))

    def test_present_values(self):
        self.assertEqual(m.present_value().display()['현재가치'],'5,583,948원')
        self.assertEqual(m.present_value('annuity',300000).display()['현재가치'],'2,340,508원')
        self.assertEqual(m.present_value('annuity',300000,beginning=False).display()['현재가치'],'2,208,026원')
        self.assertEqual(m.present_value('annuity',300000,rate=0).metrics['현재가치'],D(3000000))

    def test_emergency(self):
        r=m.emergency(3000000,cash=20000000)
        self.assertEqual(r.metrics['부족한 비상자금'],0)
        self.assertAlmostEqual(float(r.metrics['목표 대비 충족률']),111.111111,places=5)
        r=m.emergency(3000000,cash=20000000,debt=25000000)
        self.assertEqual(r.metrics['순유동자산'],0)
        self.assertEqual(r.metrics['부족한 비상자금'],18000000)

    def test_goals_and_opportunity(self):
        self.assertEqual(m.goals([dict(target=100000000)]).display()['매달 필요한 저축액'],'681,682원')
        r=m.opportunity(300000)
        self.assertEqual(r.display()['기간 후 모였을 금액'],'110,032,388원')
        self.assertEqual(r.rows[0]['지연 후 자금'].quantize(D(1)),D(73827146))
        self.assertEqual(m.opportunity(300000,years=5).rows[0]['목표 달성 월 납입액'],'남은 기간 없음')

    def test_validation_and_zero(self):
        for invalid in ('nan','Infinity',-1):
            with self.assertRaises(ValueError):m.num(invalid)
        with self.assertRaises(ValueError):m.tvm('period',principal=0,payment=0,target=100)
        with self.assertRaises(ValueError):m.emergency(0)
        with self.assertRaises(ValueError):m.tvm('future',years=1.01)
        self.assertEqual(m.tvm('payment',target=1200,rate=0,years=1).metrics['필요 정기 납입액'],100)
        self.assertEqual(m.tvm('period',principal=100,target=100).metrics['필요 납입 횟수'],0)

if __name__=='__main__':unittest.main()
