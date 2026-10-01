"""Real Streamlit 1.64 runtime tests. Run separately from stub-based tests.

python -m pytest -q tests/test_streamlit_runtime.py
CI sets HW_REQUIRE_PINNED_RUNTIME=1, so a missing/mismatched runtime fails rather
than silently being reported as verified. This test file never installs a stub.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
REQUIRED=os.environ.get('HW_REQUIRE_PINNED_RUNTIME')=='1'
try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except (ImportError,AttributeError):
    if REQUIRED: raise RuntimeError('Real pinned Streamlit is required for this gate')
    pytest.skip('Real Streamlit unavailable; not a runtime PASS',allow_module_level=True)
if not getattr(st,'__version__',None) or hasattr(st,'_api'):
    raise RuntimeError('A test stub cannot run the real-runtime suite; use a separate process')
if REQUIRED and (sys.version_info[:2]!=(3,12) or st.__version__!='1.64.0'):
    raise RuntimeError('This gate requires Python 3.12 and Streamlit 1.64.0')
CATALOG=json.loads((ROOT/'FINANCIAL_CALCULATORS_CATALOG.json').read_text(encoding='utf-8'))
ITEMS=[item for group in CATALOG['groups'] for item in group['calculators']]
ID_BY_NAME={item['name']:item['id'] for item in ITEMS}


def app(name=None,isolated=False):
    at=AppTest.from_file(ROOT/'calculator_app.py',default_timeout=30)
    if name:at.query_params['calc']=ID_BY_NAME[name]
    if isolated:at.query_params['view']='single'
    return at.run()


def healthy(at):
    assert not at.exception,[(e.message) for e in at.exception]


@pytest.mark.parametrize('item',ITEMS,ids=lambda item:item['id'])
@pytest.mark.parametrize('isolated',[False,True],ids=['normal','single'])
def test_all_88_first_render_real_runtime(item,isolated):
    at=app(item['name'],isolated);healthy(at)
    if isolated:
        assert not at.sidebar.button
        assert not [b for b in at.button if b.key=='jc_back_catalog']
        assert not [b for b in at.button if b.key=='jc_transfer_apply']
    else:assert any(b.key=='jc_back_catalog' for b in at.button)


def test_search_is_home_only_and_sidebar_resets_it():
    at=app();healthy(at)
    at.text_input(key='jc_search').input('증여').run();healthy(at)
    at.button(key='calc_sidebar_group_2').click().run();healthy(at)
    assert not [i for i in at.text_input if i.key=='jc_search']
    assert at.session_state['jc_catalog_query']==''
    at.button(key='calc_sidebar_home').click().run();healthy(at)
    assert at.text_input(key='jc_search').value==''


@pytest.mark.parametrize('name',['적정보험료계산기','정기·종신 비교계산기','총 납입보험료계산기','납입면제 효과계산기'])
def test_premium_exact_won_real_widgets(name):
    at=app(name);healthy(at)
    premium=[i for i in at.number_input if '보험료' in i.label and '(원)' in i.label]
    assert premium,'Premium must expose exact won input, not rounded manwon'
    premium[0].set_value(123456).run();healthy(at)
    assert [i for i in at.number_input if i.key==premium[0].key][0].value==123456
    calc=[b for b in at.button if b.label=='계산하기']
    assert calc and not calc[0].disabled
    calc[0].click().run();healthy(at)
    assert at.metric


def test_draft_after_actual_widget_cleanup():
    at=app('가족 생활자금계산기');healthy(at)
    money=[i for i in at.number_input if '월 생활비' in i.label][0]
    key=money.key
    money.set_value(321.0).run();healthy(at)
    at.button(key='jc_back_catalog').click().run();healthy(at)
    from modules.calculators.catalog_browser import card_key
    at.button(key=card_key('가족 생활자금계산기')+'_open_here').click().run();healthy(at)
    assert at.number_input(key=key).value==321.0


def test_invalid_single_link_never_opens_catalog():
    at=AppTest.from_file(ROOT/'calculator_app.py',default_timeout=30)
    at.query_params.update(calc='does-not-exist',view='single');at.run();healthy(at)
    assert at.error
    assert not at.sidebar.button
    assert not [i for i in at.text_input if i.key=='jc_search']


def test_workspace_login_guard_remains():
    at=AppTest.from_file(ROOT/'app.py',default_timeout=30).run();healthy(at)
    assert any(i.label=='비밀번호' for i in at.text_input)
    assert not any(t.key=='hw_admin_settings_open' for t in at.toggle)


def test_workspace_test_login_and_existing_admin_settings():
    at=AppTest.from_file(ROOT/'app.py',default_timeout=30)
    at.secrets['passwords']={'Admin':'RUNTIME_TEST_ONLY_not_a_real_secret!'}
    at.run();healthy(at)
    [i for i in at.text_input if i.label=='비밀번호'][0].input('RUNTIME_TEST_ONLY_not_a_real_secret!')
    [b for b in at.button if b.label.startswith('워크스페이스 시작')][0].click().run();healthy(at)
    assert at.session_state['password_correct'] is True
    at.toggle(key='hw_admin_settings_open').set_value(True).run();healthy(at)
    assert any(i.label=='공통 PDF 출력 브랜드명' for i in at.text_input)


def test_clear_does_not_export_previous_quick_result():
    at=app('가족 생활자금계산기');healthy(at)
    [b for b in at.button if b.label=='계산하기'][0].click().run();healthy(at)
    assert at.metric
    at.button(key='a_clear_family').click().run();healthy(at)
    assert not at.metric
    assert [b for b in at.button if b.label=='계산하기'][0].disabled
