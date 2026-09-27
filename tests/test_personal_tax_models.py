import unittest
from decimal import Decimal as D
from modules.personal_tax_models import isa, financial, progressive_tax, NAMES, ISA


class PersonalTaxTests(unittest.TestCase):
    def test_isa_observed_general_qualified_and_cap(self):
        for years, allowance, profit, tax in ((5,2000000,11604218,1055291),
                                            (5,4000000,11802218,857291),
                                            (6,4000000,15862467,1303423)):
            r=isa(years=years,allowance=allowance)
            self.assertLess(abs(r.metrics['ISA 세후 수익']-profit),D('.51'))
            self.assertLess(abs(r.metrics['ISA 세금 (지방세 포함)']-tax),D('.51'))
            self.assertEqual(r.metrics['총 납입액'],100000000)
            self.assertEqual(sum(x['해당 연도 납입액'] for x in r.rows),100000000)
        self.assertEqual(isa(years=6).rows[-1]['해당 연도 납입액'],0)

    def test_isa_constraints_and_no_returns(self):
        r=isa(rate=0)
        self.assertEqual(r.metrics['ISA 세금 (지방세 포함)'],0)
        self.assertEqual(r.metrics['ISA 세후 만기 자금'],100000000)
        self.assertEqual(r.metrics['ISA 이용 시 만기 자금 차이'],0)
        for kwargs in ({'years':2},{'years':3.5},{'annual':20000001},{'allowance':3000000}):
            with self.assertRaises(ValueError):isa(**kwargs)

    def test_financial_reference_and_comparison_branch(self):
        r=financial()
        self.assertEqual(r.metrics['국세·지방세 합계 (공제 전 추정)'],11396000)
        self.assertEqual(r.metrics['일반 원천징수 대비 추가 부담'],621500)
        self.assertEqual(r.metrics['금융소득에 따른 세부담 증가분'],4779500)
        # Low other income: comparison method dominates, not the progressive formula.
        r=financial(30000000,0,0)
        self.assertEqual(r.metrics['국세 산출세액'],4200000)
        self.assertEqual(r.metrics['일반 원천징수 대비 추가 부담'],0)
        for interest in (0,19999999,20000000,20000001):
            r=financial(interest,0,0)
            self.assertEqual(r.metrics['국세 산출세액'],D(interest)*D('.14'))

    def test_brackets(self):
        for base,expected in ((0,0),(14000000,840000),(50000000,6240000),
                              (88000000,15360000),(150000000,37060000),
                              (300000000,94060000),(500000000,174060000),
                              (1000000000,384060000)):
            self.assertEqual(progressive_tax(base),expected)
            self.assertGreater(progressive_tax(base+1),expected)

    def test_center_views_and_snapshot(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_string('from modules.jarvia_calculator_center import run\nrun(lambda:None)').run()
        for name in NAMES:
            at.selectbox(key='jc_selected').select(name).run()
            at.button[0].click().run()
            self.assertFalse(at.exception)
            self.assertTrue(at.metric)
            self.assertEqual([t.label for t in at.tabs],['고객용 결과','설계사용 상세 계산'])
            self.assertEqual(len(at.get('download_button')),2)
        at.selectbox(key='jc_selected').select(ISA).run()
        at.selectbox(key='cov_'+ISA+'_3').select('서민형·농어민 요건 충족 400만원').run()
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value,'11,802,218원')

class GrossupIntegration(unittest.TestCase):
    def test_eligible_dividend_shared_engine(self):
        from modules.dividend_grossup import finance_tax
        from modules.shareholder_distribution import distribution, MODES
        r=financial(5000000,0,100000000,1500000,100000000)
        expected=finance_tax(5000000,100000000,100000000,1500000)
        self.assertEqual(r.metrics['배당가산액'],8500000)
        self.assertEqual(r.metrics['배당세액공제'],expected['배당세액공제'])
        before=financial(5000000,0,100000000,1500000)
        shareholder=distribution(100000000,0,5000000,100000000,1500000,MODES[3])
        self.assertEqual(shareholder['개인세 증가 추정'],r.metrics['국세·지방세 합계 (공제 전 추정)']-before.metrics['국세·지방세 합계 (공제 전 추정)'])
        self.assertEqual(financial(0,0,0,1500000,20000000).metrics['배당세액공제'],0)
