"""Shared home search and readable insurer workspace, backed by one catalog."""
import html
from functools import lru_cache
import streamlit as st
from modules.resources.portal_repository import load_catalog, filter_insurers, safe_url
from modules.shared.workspace_tools import field, session_notice
from modules.shared.ui_components import page_header


def _clear_home_search():st.session_state['home_insurer_search']=''


def render_home_quick_search():
    data,issues=load_catalog()
    left,right=st.columns([10,1])
    query=left.text_input('보험사 검색',placeholder='보험사·별칭·대표번호 검색',key='home_insurer_search',label_visibility='collapsed').strip()
    if query:right.button('×',key='clear_home_insurer_search',on_click=_clear_home_search,help='검색어 지우기')
    if issues:st.caption('일부 포털 항목을 확인해야 합니다. 포털의 기준일 화면을 참고하세요.')
    if not query:return
    rows=filter_insurers(data['insurers'],query)
    if not rows:
        st.info('일치하는 보험사가 없습니다. 이름·별칭·번호로 다시 검색해 주세요.')
        return
    cards = []
    for row in rows[:6]:
        name = html.escape(row['name'])
        url = html.escape(safe_url(row['url']), quote=True)
        main = row['group'] == '기본 포털'
        logo = '<span class="hw-home-portal-mark">H</span>' if main else _logo(row)
        detail = '<span class="hw-home-portal-badge">기본 포털</span>' if main else html.escape(row['phone'] or '')
        cards.append(f'<a class="hw-home-portal-row" href="{url}" target="_blank" rel="noopener noreferrer" aria-label="{name} 전산 열기 새 탭"><span class="hw-home-portal-logo">{logo}</span><strong>{name}</strong><span class="hw-home-portal-meta">{detail}</span><span class="hw-home-portal-arrow" aria-hidden="true">↗</span></a>')
    st.markdown("""<style>
    .hw-home-portal-results{display:grid;gap:7px;margin:3px 0 0}
    .hw-home-portal-results .hw-home-portal-row{display:flex;align-items:center;gap:11px;box-sizing:border-box;min-height:56px;padding:8px 11px;border:1px solid #d9e5f1;border-radius:13px;background:#fff;color:#173b59!important;text-decoration:none!important;transition:background-color .16s,border-color .16s}
    .hw-home-portal-row:hover{background:#f5f9ff!important;border-color:#9dbfe4!important}
    .hw-home-portal-row:focus-visible{outline:3px solid #2867c5;outline-offset:2px}
    .hw-home-portal-logo{display:grid;place-items:center;flex:0 0 38px;height:38px;border:1px solid #e3ecf5;border-radius:10px;background:#fbfdff;overflow:hidden}
    .hw-home-portal-logo img{width:30px;height:30px;object-fit:contain}
    .hw-home-portal-mark{display:grid;place-items:center;width:38px;height:38px;background:linear-gradient(130deg,#1769de,#10969c);color:#fff;font-size:16px;font-weight:750}
    .hw-home-portal-row strong{font-size:14px!important;line-height:1.4!important;flex:1;min-width:0;word-break:keep-all;overflow-wrap:anywhere}
    .hw-home-portal-meta{font-size:12px!important;font-weight:650;color:#6b849a;white-space:nowrap}
    .hw-home-portal-badge{display:inline-block;padding:4px 8px;border-radius:12px;background:#edf4ff;color:#1769df;font-size:11px;font-weight:700}
    .hw-home-portal-arrow{font-size:12px;color:#7894af}
    @media(max-width:420px){.hw-home-portal-results .hw-home-portal-row{gap:8px;padding:8px}.hw-home-portal-row strong{font-size:13px!important}.hw-home-portal-meta{font-size:11px!important}}
    @media(prefers-reduced-motion:reduce){.hw-home-portal-row{transition:none!important}}
    </style><div class="hw-home-portal-results">""" + ''.join(cards) + '</div>', unsafe_allow_html=True)
    if len(rows)>6:
        st.caption(f'검색 결과 {len(rows)}개 중 6개 표시 · 전체 결과는 원수사·공식자료 포털에서 확인하세요.')




@lru_cache(maxsize=64)
def _logo_cached(slug: str, fallback: str) -> str:
    import base64
    from modules.shared.paths import PROJECT_ROOT
    path=PROJECT_ROOT/'assets'/'insurer_logos'/(slug+'.png')
    if path.is_file():
        encoded=base64.b64encode(path.read_bytes()).decode('ascii')
        return f'<img src="data:image/png;base64,{encoded}" alt="" loading="lazy">'
    return '<span>'+html.escape(fallback[:1])+'</span>'

def _logo(row):
    return _logo_cached(str(row.get('slug') or ''),str(row.get('name') or ''))


def run():
    data, issues = load_catalog()
    page_header('업무 지원', '원수사·공식자료 포털', '보험사 전산과 업무에 필요한 공식 자료를 한곳에서 확인하세요.', 'IP')
    session_notice('f_')
    modes = ['전산 접속', '공식기관·공공자료', '서식', '즐겨찾기', '기준일']
    if st.session_state.get('f_mode') not in modes:
        st.session_state['f_mode'] = '전산 접속'
    mode = st.radio('업무 자료 선택', modes, horizontal=True, key='f_mode')
    if mode in ('공식기관·공공자료', '서식', '기준일'):
        from modules.resources.official_resources import render_resources
        render_resources(data, mode, issues)
        return
    for issue in issues:
        st.warning(issue)
    search_col, filter_col = st.columns([3,1])
    with search_col:
        query = field('text_input', '보험사·별칭·대표번호 검색', 'f_search', '', max_chars=100)
    with filter_col:
        group = field('selectbox', '보험사 구분', 'f_group', '전체', options=['전체', '기본 포털', '생명보험', '손해보험'])
    if mode == '즐겨찾기':
        with st.expander('즐겨찾기 설정'):
            columns = st.columns(3)
            for i, row in enumerate(data['insurers']):
                with columns[i % 3]:
                    field('checkbox', row['name'], 'f_favorite_'+row['slug'], False)
    rows = filter_insurers(data['insurers'], query, group)
    if mode == '즐겨찾기':
        rows = [r for r in rows if st.session_state.get('f_favorite_'+r['slug'], False)]
    portal_grid(rows)
