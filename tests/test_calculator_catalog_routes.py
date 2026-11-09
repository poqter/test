"""Every catalog route: synthetic examples, exports and denied group access.

This checks UI execution, not independent legal or actuarial certification.
Never substitute these fixtures for signed-in production account testing.
"""
import pytest
from streamlit.testing.v1 import AppTest
from modules.calculators.hwarang_calculator_center import ITEMS

CONFIRMATIONS = {
    '해외금융계좌 신고계산기': {4: '거주자·내국법인, 면제 없음 확인', 6: '확인'},
    '비상장주식 평가계산기': {23: '확인'},
    '인정이자계산기': {9: '예'},
    '급여vs배당 비교계산기': {14: '확인'},
    '가지급금 정밀진단계산기': {4: '예'},
    '주식매수선택권계산기': {10: '확인'},
}

def open_calculator(name, allowed=True):
    return AppTest.from_string(f'''
import streamlit as st
from modules.shared.permissions import CALCULATOR_GROUP_PERMISSION
st.session_state['hw_feature_permissions'] = list(CALCULATOR_GROUP_PERMISSION.values()) if {allowed!r} else []
from modules.calculators.hwarang_calculator_center import run
run(isolated=True, fixed_name={name!r})
''', default_timeout=30).run()

@pytest.mark.parametrize('name', tuple(ITEMS))
def test_every_catalog_example_calculates_and_exports(name):
    app = open_calculator(name)
    assert not app.exception
    example = [b for b in app.button if b.label == '예시 입력']
    if example:
        example[0].click().run()
    submit = [b for b in app.button if ('계산' in b.label or '분석' in b.label) and not b.disabled]
    assert len(submit) == 1, name
    key = submit[0].key
    app.button(key=key).click().run()
    if name in CONFIRMATIONS:
        assert app.error, 'Unconfirmed eligibility must not produce a result'
        assert not app.get('download_button')
        for index, value in CONFIRMATIONS[name].items():
            app.selectbox(key=f'cov_{name}_{index}').select(value)
        app.run()
        app.button(key=key).click().run()
    assert not app.exception
    assert not app.error, [x.value for x in app.error]
    assert app.get('download_button'), 'A result export must be available'
    clear = [b for b in app.button if b.label == '초기화']
    if clear:
        clear[0].click().run()
        assert not app.exception
        assert not app.get('download_button'), 'Cleared inputs must not export stale results'

@pytest.mark.parametrize('name', tuple(ITEMS))
def test_every_catalog_route_denies_missing_group_permission(name):
    app = open_calculator(name, allowed=False)
    assert not app.exception
    assert any('권한' in x.value for x in app.warning)
    assert not app.button
    assert not app.number_input
    assert not app.get('download_button')
