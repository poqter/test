"""Shared task-page layout primitives; independent of calculation state."""
from contextlib import contextmanager
import streamlit as st


def work_panels(key):
    from modules.shared.clean_design import apply_clean_design
    apply_clean_design()
    with st.container(key='hw_split_'+key):
        left, right = st.columns([1.15, 1], gap='medium')
        inputs = left.container(key='hw_surface_'+key+'_inputs')
        results = right.container(key='hw_surface_'+key+'_results')
        with results:
            hint = st.empty()
            hint.info('입력 조건을 확인하고 실행하면 이곳에서 결과를 볼 수 있습니다.')
    @contextmanager
    def result_context():
        hint.empty()
        with results:
            yield
    return inputs, result_context()
