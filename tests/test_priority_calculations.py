"""Independent arithmetic oracles for frequently discussed consultation tools.

Tax and return percentages are supplied assumptions, not assertions of law.
"""
from decimal import Decimal as D, localcontext, ROUND_DOWN
import pytest
from modules.calculators.finance.finance_models import compound, tvm, present_value
from modules.calculators.finance.finance_calculator_ui import _rows_for_display
from modules.calculators.comparison.deposit_vs_shortpay import compare_equal_cashflows
from modules.calculators.comparison.renewal_vs_nonrenewal import _calculate_periods
from modules.calculators.comparison.silson_generation_comparison import calculate
from modules.consultation.remodeling_model import Person, NewPlan, combined, money

@pytest.mark.parametrize('rate', [0, -10, 5, 100])
@pytest.mark.parametrize('beginning', [False, True])
def test_finance_matches_period_by_period_cashflow(rate, beginning):
    with localcontext() as ctx:
        ctx.prec=60
        balance=D(10000000); r=D(rate)/1200
        for _ in range(120):
            if beginning: balance+=200000
            balance*=1+r
            if not beginning: balance+=200000
        result=tvm('future',principal=10000000,payment=200000,years=10,rate=rate,beginning=beginning)
        assert abs(result.metrics['예상 최종 자금']-balance)<D('.000001')
        assert result.rows[-1]['총 자금']==result.metrics['예상 최종 자금']

@pytest.mark.parametrize('frequency',[1,12,365])
def test_permitted_extreme_results_render_in_metrics_and_rows(frequency):
    result=compound(10**12,120,100,frequency)
    with localcontext() as ctx:
        ctx.prec=100
        expected=(D(10**12)*(1+D(1)/frequency)**(120*frequency))
        # The calculation intentionally uses 48 significant digits.
        actual=result.metrics['예상 최종 자금']
        assert abs((actual-expected)/expected)<D('1e-40')
        display=f'{actual.quantize(D(1),rounding=ROUND_DOWN):,}'
    assert result.display()['예상 최종 자금']==display+'원'
    assert _rows_for_display(result)[-1]['총 자금']==display

@pytest.mark.parametrize('mode', ['payment','principal'])
def test_zero_interest_inverse_and_rounding(mode):
    args=dict(target=12000000,years=10,rate=0)
    result=tvm(mode,**args)
    assert result.metrics['예상 최종 자금']==12000000
    assert present_value(amount=12000000,years=10,rate=0).metrics['현재가치']==12000000

@pytest.mark.parametrize('reinvest',[False,True])
@pytest.mark.parametrize('years',[1,5,10])
def test_equal_contributions_match_annual_cashflow_ledger(reinvest,years):
    result=compare_equal_cashflows(100,3,years,122.45,reinvest,15.4,0)
    balance=0
    for year in range(1,11):
        contribution=1200 if year<=years else 0
        interest=(balance*.03 if reinvest else 0)+(19.5 if year<=years else 0)
        balance+=contribution+interest*.846
        assert result['rows'][year-1]['보유자산']==pytest.approx(balance)
    assert result['insurance_assets']==pytest.approx(1200*years*1.2245)

@pytest.mark.parametrize('cycle',[5,10,15,20,30])
def test_renewal_final_partial_period_and_direct_premiums(cycle):
    periods=_calculate_periods(39,80,cycle,2,10000,'가입제안서 직접 입력','기준 상승',[20000]*20)
    assert sum(p.years for p in periods)==41
    assert periods[-1].end_age==80
    assert sum(p.total for p in periods)==10000*24+20000*39*12

@pytest.mark.parametrize('amount',[0,1,1000000,10**9])
def test_silson_arithmetic_conserves_expenses(amount):
    medical={'급여':amount,'중증 비급여':amount*2,'비중증 비급여':amount*3,'보상 제외 가능 비급여':amount*4}
    payout,burden=calculate(medical,{'급여':20,'중증 비급여':30,'비중증 비급여':50})
    assert payout+burden==pytest.approx(sum(medical.values()))
    assert burden==pytest.approx(amount*6.3)

def test_remodeling_custom_months_and_household_sums():
    a=Person('A',139662,33518880,54612,13106880,[NewPlan('신규',10000,20,15)])
    b=Person('B',0,0,0,0,[])
    assert a.after_monthly==64612 and a.after_total==13256880
    assert combined([a,b])['after_total']==13256880
    assert money('100,000원')==100000
    for value in ['1,00','-1','1.5','NaN']:
        with pytest.raises(ValueError):money(value)


def test_extreme_result_renders_downloads_without_exception():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
from modules.calculators.finance.finance_models import compound
from modules.calculators.finance.finance_calculator_ui import render_result
args=dict(principal=10**12,years=120,rate=100,frequency=12)
render_result('복리계산기',compound(**args),'2026-11-09',args,'boundary')
''',default_timeout=20).run()
    assert not app.exception
    assert len(app.get('download_button'))==2
