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

def portal_grid(rows):
    """Compact, whole-card links matching the approved life/nonlife directory."""
    esc = html.escape
    mains = [r for r in rows if r['group'] == '기본 포털']
    blocks = []
    for row in mains:
        blocks.append(f'<a class="hwip-main" href="{esc(safe_url(row["url"]),quote=True)}" target="_blank" rel="noopener noreferrer"><span class="hwip-mark">H</span><span class="hwip-main-copy"><small>DEFAULT SALES PORTAL</small><strong>{esc(row["name"])}</strong><span>영업 업무를 시작하는 기본 포털</span></span><span class="hwip-main-action">영업 포털 열기 ↗</span></a>')
    panels = []
    for group in ('생명보험', '손해보험'):
        subset = [r for r in rows if r['group'] == group]
        if not subset:
            continue
        cards = []
        for row in subset:
            badge = '<span class="hwip-badge">Edge 전용</span>' if row.get('edge_only') else ''
            if row.get('notice'):
                badge = '<span class="hwip-badge hwip-warning">확인 필요</span>'
            notice = ' hwip-notice' if row.get('notice') else ''
            cards.append(f'<a class="hwip-card{notice}" href="{esc(safe_url(row["url"]),quote=True)}" target="_blank" rel="noopener noreferrer" aria-label="{esc(row["name"],quote=True)} 전산 열기 새 탭" title="{esc(row.get("note", ""),quote=True)}"><span class="hwip-logo">{_logo(row)}</span><span class="hwip-name"><strong>{esc(row["name"])}</strong>{badge}</span><span class="hwip-meta"><span>{esc(row["phone"] or "")}</span><small>전산 열기 ↗</small></span></a>')
        panels.append(f'<section class="hwip-panel"><div class="hwip-panel-head"><div><small>INSURANCE NETWORK</small><h3>{group}</h3></div><span>{len(subset)}개사</span></div><div class="hwip-cards">{"".join(cards)}</div></section>')
    if not rows:
        st.info('검색·분류 조건에 맞는 보험사가 없습니다.')
        return
    st.markdown(PORTAL_CSS + '<div class="hwip-directory">' + ''.join(blocks) + '<div class="hwip-panels">' + ''.join(panels) + '</div></div>', unsafe_allow_html=True)
    st.caption('보험사별 접속 정책과 보안 프로그램에 따라 로그인 방식이 다를 수 있습니다. 번호·주소 확인 정보는 기준일 메뉴에서 확인하세요.')


PORTAL_CSS = """<style>
.hwip-directory{margin:8px 0 0;color:#173b59}
.hwip-directory a{text-decoration:none!important;color:inherit!important}
.hwip-main{display:flex;align-items:center;gap:16px;padding:22px 20px;border:1px solid #b5d5f7;border-radius:20px;background:linear-gradient(110deg,#f4f9ff,#effafa);margin-bottom:18px}
.hwip-mark{display:grid;place-items:center;flex:0 0 50px;height:50px;border-radius:13px;background:linear-gradient(130deg,#1769de,#10969c);color:#fff;font-size:21px;font-weight:750}
.hwip-main-copy{display:grid;gap:4px;flex:1;min-width:0}.hwip-main-copy small{font-size:9px;letter-spacing:.13em;font-weight:750;color:#1765cd}.hwip-main-copy strong{font-size:18px}.hwip-main-copy>span{font-size:12px;color:#7390a8}
.hwip-main-action{background:#1969df;color:#fff;padding:14px 18px;border-radius:12px;font-size:13px;font-weight:700;white-space:nowrap}
.hwip-panels{display:grid;grid-template-columns:1.18fr 1fr;align-items:start;gap:18px}
.hwip-panel{background:linear-gradient(125deg,#fff,#f8fbff);border:1px solid #cadceb;border-radius:22px;padding:18px;min-width:0;box-shadow:0 12px 30px #173b5910}
.hwip-panel-head{display:flex;align-items:end;justify-content:space-between;padding:9px 3px 16px}.hwip-panel-head small{font-size:9px;letter-spacing:.12em;color:#5181a7;font-weight:750}.st-key-hw_task_page .hwip-panel-head h3{font-size:27px!important;color:#4b83ac!important;line-height:1.3;margin:6px 0 0;padding:0;font-weight:700!important}.hwip-panel-head>span{font-size:12px;font-weight:650;color:#7890a5}
.hwip-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.hwip-card{display:flex;align-items:center;gap:11px;border:1px solid #cedff0;border-radius:15px;padding:13px 11px;min-height:80px;box-sizing:border-box;background:#fff;transition:border-color .16s,background-color .16s;min-width:0}
.hwip-card:hover{border-color:#7daadd;background:#f3f8ff}.hwip-directory a:focus-visible{outline:3px solid #2867c5;outline-offset:3px}.hwip-logo{display:grid;place-items:center;flex:0 0 44px;height:44px;border:1px solid #e0ebf5;border-radius:12px;background:#fbfdff;overflow:hidden}.hwip-logo img{width:34px;height:34px;object-fit:contain}.hwip-name{display:flex;flex-direction:column;gap:8px;min-width:0;flex:1}.hwip-name strong{font-size:13px;line-height:1.45;word-break:keep-all;overflow-wrap:anywhere}.hwip-meta{display:flex;flex-direction:column;align-items:end;gap:11px;flex-shrink:0;color:#6b849a}.hwip-meta>span{font-size:11px;font-weight:700}.hwip-meta small{font-size:10px}.hwip-badge{align-self:start;font-size:9px;padding:3px 6px;border-radius:9px;background:#edf5fc;color:#35648d}.hwip-warning{background:#fff0d1;color:#9b691b}.hwip-card.hwip-notice{background:#fffbf3;border-color:#ecd3a4}
@media(max-width:1250px){.hwip-panels{grid-template-columns:1fr}.hwip-name strong{font-size:14px}}
@media(max-width:600px){.hwip-cards{grid-template-columns:1fr}.hwip-panel{padding:14px}.hwip-main{flex-wrap:wrap;padding:16px}.hwip-main-action{margin-left:66px}.hwip-meta>span{font-size:12px}}
@media(prefers-reduced-motion:reduce){.hwip-card{transition:none}}
</style>"""



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
