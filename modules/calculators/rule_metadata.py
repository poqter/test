"""Source-declared scope and rule-pack metadata, not a legal verification claim."""
from functools import lru_cache
from html import escape
import json
from pathlib import Path

@lru_cache(maxsize=1)
def _pack():
    return json.loads((Path(__file__).resolve().parents[2] / 'data/calculator_rules.json').read_text(encoding='utf-8'))


def rule_for(name):
    return _pack()['calculators'].get(name, {})


def render_scope(name):
    import streamlit as st
    record = rule_for(name)
    if not record:
        return
    year = f"{record['income_year']}년 기준 · " if record.get('income_year') else ''
    st.markdown('<div class="hw-scope-label">' + escape(year + '입력한 조건 범위의 계산 · 규칙 ' + record['rule_version']) + '</div>', unsafe_allow_html=True)
    with st.expander('적용 범위 · 계산 기준'):
        st.write(record['applies_to'])
        for note in record.get('limitations', []):
            st.caption(note)
        st.caption('법령 대조일은 원본 코드에 기재된 날짜입니다. 이 버전은 입력·표시·검증 구조 개선이며 새로운 법령 전수 검증 완료를 뜻하지 않습니다.')
        if record.get('source_declared_review_date'):
            st.caption('원본 기재 대조일: ' + record['source_declared_review_date'])
        for url in record.get('source_urls', []):
            st.markdown('[관련 공식 기준](' + url + ')')
