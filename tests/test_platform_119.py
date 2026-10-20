from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from streamlit.testing.v1 import AppTest
from modules.calculators.corporate.carryforward_loss import losses
from modules.calculators.comparison.deposit_vs_shortpay import compare_equal_cashflows
from modules.briefing.clustering import _same_release


def test_empty_loss_ledger_is_no_losses():
    result=losses('')
    assert result.metrics['당기 공제액']==0
    assert result.metrics['공제 후 과세표준']==300000000
    assert result.rows==[]


def test_loss_ledger_keeps_invalid_and_duplicates_visible():
    for raw in ['2025','2025,1;2025,2','2026,1','2025,-1']:
        with pytest.raises(ValueError):losses(raw)
    assert losses('2025,1000000').metrics['당기 공제액']==1000000


def test_equal_cashflows_zero_rate_and_full_refund():
    r=compare_equal_cashflows(100,0,5,100)
    assert r['principal']==r['deposit_assets']==r['insurance_assets']==6000
    assert sum(x['연간 납입'] for x in r['rows'])==6000
    assert all(x['연간 납입']==0 for x in r['rows'][5:])


def test_reinvestment_and_tax_have_expected_effect_without_new_deposits():
    simple=compare_equal_cashflows(100,3,5,120,False)
    reinvest=compare_equal_cashflows(100,3,5,120,True)
    no_tax=compare_equal_cashflows(100,3,5,120,True,0,0)
    assert simple['deposit_assets']<reinvest['deposit_assets']<no_tax['deposit_assets']
    assert reinvest['insurance_assets']<no_tax['insurance_assets']
    assert simple['rows'][4]['보유자산']==simple['rows'][-1]['보유자산']


def test_macro_clustering_requires_same_country_period_and_observation():
    now=datetime(2026,10,15,tzinfo=timezone.utc)
    def c(title,days=0):return SimpleNamespace(title=title,published_at=now+timedelta(days=days))
    assert _same_release(c('미국 9월 CPI 상승'),c('美 9월 소비자물가 발표'))
    for title,days in [('한국 9월 소비자물가',0),('미국 8월 CPI',0),('미국 9월 근원 CPI',0),('미국 9월 CPI 예상',0),('미국 9월 CPI 상승',5),('미국 CPI 상승',0)]:
        assert not _same_release(c('미국 9월 CPI 상승'),c(title,days))


def test_loss_empty_table_example_and_export_snapshot():
    at=AppTest.from_string('''
from modules.calculators.coverage.coverage_calculator_ui import run
from modules.calculators.corporate.carryforward_loss import FIELDS,calculate,NAME
run(NAME,fields=FIELDS,calculator=calculate)
''').run()
    assert not at.exception
    assert any('미사용 결손금: 없음' in x.value for x in at.markdown)
    at.button(key='calculate_이월결손금계산기').click().run()
    assert not at.exception and not at.error
    assert at.session_state['coverage_result_이월결손금계산기'][0][0]==''
    at.button(key='ux_example_이월결손금계산기').click().run()
    assert any('미사용 결손금: 1건' in x.value for x in at.markdown)
    at.button(key='calculate_이월결손금계산기').click().run()
    assert at.session_state['coverage_result_이월결손금계산기'][0][0]=='2025,500000000'
    at.button(key='ux_clear_이월결손금계산기').click().run()
    assert not at.exception
    assert any('미사용 결손금: 없음' in x.value for x in at.markdown)


def test_education_ui_completion_and_navigation_offline():
    code='''
import json,copy
from pathlib import Path
from unittest.mock import patch
import streamlit as st
from hwarang_academy.education import ui
items=json.loads((Path(ui.__file__).parent/'catalog.json').read_text())
permissions={'academy.new_hire','academy.library','academy.my_learning','academy.simulator'}
def rpc(auth,owner,name,**kw):
    if name=='complete':st.session_state.setdefault('done',[]).append(kw['p_lesson']);return
    for item in items:
        if item['id']=='foundation-new_hire':item['progress']={'completed_lessons':st.session_state.get('done',[])}
    return items
with patch.object(ui,'rpc',rpc):
    ui.render(None,'test',permissions,{'role':'user'},st.session_state.get('_academy_surface','courses'))
'''
    at=AppTest.from_string(code).run();assert not at.exception
    at.checkbox(key='read_foundation-new_hire_1').check().run()
    at.button(key='complete_foundation-new_hire_1').click().run()
    assert not at.exception and at.session_state['done']==['1']
    at.session_state['_academy_surface']='library';at.run()
    assert not at.exception
    assert len(at.get('download_button'))==3
    at.text_input[0].set_value('없는 자료').run()
    assert len(at.get('download_button'))==0
    at.session_state['_academy_surface']='my_learning';at.run()
    assert not at.exception


def test_anonymous_analyzer_fixture_roundtrip():
    from modules.consultation.analyzer_sample import sample_workbook
    from modules.consultation.analyzer_model import _parse_source_file_uncached
    parsed=_parse_source_file_uncached(sample_workbook())
    assert len(parsed['contracts'])==2
    assert sum(c['monthly'] for c in parsed['contracts'])==150000
    assert len(parsed['coverages'])==3
    assert any(c['group']=='기타' for c in parsed['coverages'])


def test_question_templates_preserve_order_and_reject_oversize():
    from modules.consultation.question_studio import parse_question_template
    assert parse_question_template(json.dumps({'schema':'hwarang-questions-1','questions':[' B ','A']}))==['B','A']
    for raw in ['{}','[]','bad',json.dumps({'schema':'hwarang-questions-1','questions':['x'*501]})]:
        with pytest.raises(ValueError):parse_question_template(raw)
