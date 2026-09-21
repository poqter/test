"""Shared task navigation and session-only drafts. No persisted customer data."""
import copy
import streamlit as st

PREFIXES = {
    'analyzer': ('analyzer_',), 'remodeling': ('rm_',),
    'deposit_vs_shortpay': ('hwarang_ds_', 'ds_'),
    'renewal_vs_nonrenewal': ('rn_',), 'inheritance_tax': ('it_',),
    'insurance_claim_guide': ('cg_',), 'silson_generation_comparison': ('sc_',),
}
STEPS = {
    'analyzer': ('원본 업로드', '인식·보장 확인', '고객용 결과'),
    'remodeling': ('기존·변경안 입력', '보험료·계약 변화', '비교안 다운로드'),
    'deposit_vs_shortpay': ('비교 조건 입력', '10년 가정 확인', '예상 결과 비교'),
    'renewal_vs_nonrenewal': ('현재·제안 조건', '갱신 가정', '총액·상세 비교'),
    'inheritance_tax': ('재산·공제 입력', '세액 확인', '납부재원 점검'),
    'insurance_claim_guide': ('청구 유형', '서류·담보 확인', '안내문 작성'),
    'silson_generation_comparison': ('현재·비교 조건', '의료비 예시', '보험료·보장 비교'),
    'convention': ('계약자료 등록', '확인·제외 내역', '달성·환산 결과'),
    'summer': ('계약자료 등록', '월별 필수조건', '보너스·결과'),
    'manager_results': ('실적자료 등록', '집계 대상 확인', '수금자별 결과'),
    'commission_calculator': ('예시표·계약 등록', '매칭·지급률 확인', '예상 수당'),
}

def save_page_draft(page):
    prefixes = PREFIXES.get(page, ())
    draft = {}
    for key in list(st.session_state):
        if prefixes and key.startswith(prefixes):
            value = st.session_state[key]
            # Upload and binary results stay in their existing lifecycle, never duplicate them.
            actions = ('file','upload','editor','_run','_download','_add_','_remove_',
                       '_delete_','_generate_','_apply_','_reset','_restore_','_clear_',
                       '_example','cg_claim_','_select_all','_select_default','_select_none')
            if any(token in key for token in actions) or isinstance(value, (bytes, bytearray)):
                continue
            if isinstance(value, (str, int, float, bool, list, tuple)) or value.__class__.__module__ == 'datetime':
                draft[key] = copy.deepcopy(value)
    if draft:
        st.session_state['_draft_' + page] = draft

def restore_page_draft(page):
    for key, value in st.session_state.pop('_draft_' + page, {}).items():
        st.session_state.setdefault(key, value)

@st.dialog('작업 내용 초기화')
def reset_dialog():
    st.write('모든 도구의 현재 입력·계산 결과·업로드 상태를 초기화합니다. 필요한 결과를 먼저 내려받으세요.')
    if st.button('모든 작업 초기화', type='primary', key='wb_reset_confirm'):
        keep = {k: st.session_state[k] for k in ('password_correct','login_user','active_app') if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(keep)
        st.rerun()

def render_workbench(page, definitions, allowed, navigate):
    back, related, reset = st.columns([1, 2, 1])
    if back.button('← 홈으로', key='wb_home'): navigate('home')
    choices = [k for k in allowed if k != page]
    with related:
        selected = st.selectbox('다른 도구로 이동', choices, index=None,
                                format_func=lambda k: definitions[k]['name'],
                                placeholder='도구 선택', key='wb_jump')
        if selected and st.button('선택한 도구 열기', key='wb_jump_go'):
            navigate(selected)
    if reset.button('작업 초기화', key='wb_reset'): reset_dialog()
    if page in STEPS:
        st.markdown('<div class="sig-steps">' + ''.join(f'<span class="sig-step">{i} · {step}</span>' for i, step in enumerate(STEPS[page],1)) + '</div>', unsafe_allow_html=True)

def dataset_overview(raw, candidates, excluded, review, label):
    """Show reconciliation before editing without changing calculation filters."""
    st.subheader('업로드 자료 확인')
    for col, title, value in zip(st.columns(4), ('원본 계약', '검토 후보', '기준상 제외', '후보 중 확인 필요'),
                               (len(raw), len(candidates), len(excluded), len(review))):
        col.metric(title, f'{value:,}건')
    st.caption('원본 = 검토 후보 + 기준상 제외. 확인 필요 건은 검토 후보에 포함되며, 수정 후 최종 집계가 달라질 수 있습니다.')
    if len(raw) != len(candidates) + len(excluded):
        st.warning('원본과 분류 건수가 일치하지 않습니다. 아래 내역을 확인하세요.')
    with st.expander('입력 자료 열·일부 행 확인'):
        st.write(' · '.join(str(c) for c in raw.columns if not str(c).startswith('_')))
        st.dataframe(raw.head(10), hide_index=True, use_container_width=True)
