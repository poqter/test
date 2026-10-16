'''Calculator discovery UI. Keeps navigation state separate from widget state.'''
import hashlib
import json
import re
import time
from html import escape
from urllib.parse import quote, urlsplit, urlunsplit
import streamlit as st
from modules.calculators.ux_profiles import profile
from modules.calculators.visuals import category_emoji, category_label, purpose_label

PURPOSES = (
    ('보험료·계약을 계산해요', '보험료 계약 상령일'),
    ('치료·생활자금을 준비해요', '치료비 생활자금 보장'),
    ('노후를 준비해요', '노후 은퇴 연금'),
    ('목돈을 모으고 싶어요', '목돈 저축 투자'),
    ('세금을 확인해요', '개인 부동산 세금'),
    ('상속·증여를 준비해요', '상속 증여 승계'),
    ('대표 전략을 검토해요', '대표 급여 배당 법인'),
    ('사업 실무를 점검해요', '사업 법인 실무 세액공제'),
)
RULES = (
    ('보험료 계약 상령 가입', ('보험나이', '상령일', '총 납입보험료', '납입면제', '적정보험료', '정기·종신')),
    ('치료 생활자금 보장 질병 간병', ('가족 생활자금', '교육자금', '부채 정리자금', '비상자금', '사망보장', '중대질병', '간병', '자녀보험', '의료비')),
    ('노후 은퇴 연금 퇴직', ('연금', '은퇴', '퇴직금', '크레바스', '3층연금')),
    ('목돈 저축 투자 복리 재무', ('목표자금', '복리', '미래가치', '투자수익', '수익률', '현재가치', '기회비용', 'ISA')),
    ('개인 부동산 세금 소득', ('양도소득', '근로소득', '종합소득', '임대소득', '금융소득', '주택담보', '4대보험', '취득세', '해외금융')),
    ('상속 증여 승계 물려', ('상속', '증여', '비상장주식', '가업승계', '명의신탁', '차등배당', '특정법인', '지분 매입', '승계 재원')),
    ('대표 급여 배당 법인 전략', ('인정이자', '급여vs배당', '개인사업자·법인', '임원퇴직금', '가지급금', '이익소각', '법인청산', '지주회사', '합병', '키맨', '특허권', '법인 부동산', '특수관계자', '법인보험')),
    ('사업 법인 실무 세액공제', ('창업중소기업', '성실신고', '법인세', '부가세', '업무용승용차', '접대비', '고용증대', '연구인력', '직무발명', '이월결손금', '주식매수선택권', '사내근로복지기금', '법인 4대보험', '상여금', 'DC부담금', '정책자금')),
)

def normalize(text):
    return re.sub(r'[\s·.,?]', '', text.casefold())

def initials(text):
    return ''.join('ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'[(ord(c)-44032)//588]
                   if 44032 <= ord(c) < 55204 else c for c in text)

def matches(name, group, description, item_tags, query):
    q = normalize(query)
    if not q:
        return True
    haystack = normalize(' '.join((name, group, description, *item_tags)))
    if q in haystack or q in initials(normalize(name)):
        return True
    return any(any(k in q for k in keys.split()) and any(n in name for n in names)
               for keys, names in RULES)

def card_key(name):
    return 'hwcalc_card_' + hashlib.sha256(name.encode()).hexdigest()[:12]


def calculator_deep_link(name, ids=None):
    '''Build a stable relative deep link; fall back to the current name for compatibility.'''
    value = (ids or {}).get(name, name)
    return '?calc=' + quote(value, safe='') + '&view=single'




def prepared_new_tab_url(name, ids=None):
    """Called only by an explicit dialog open/refresh. Never reuse a ticket."""
    identity = st.session_state.get('_hwarang_calculator_identity') or {}
    profile = identity.get('profile') or {}
    user_id = str(profile.get('id') or '')
    if not user_id:
        return ''
    try:
        raw = str(st.context.url)
    except AttributeError:
        raw = ''
    if not raw:
        return ''
    parts = urlsplit(raw)
    base = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
    target = base + calculator_deep_link(name, ids)
    try:
        from modules.shared.hwarang_auth import HwarangAuthService, SupabaseConfig
        auth = HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))
        url = auth.create_launch_ticket(user_id=user_id, target_app='calculator', target_url=target)
    except Exception:
        return ''
    return url


@st.dialog('계산기 새 탭 열기')
def open_new_tab(name, ids=None):
    from modules.shared.launch_link_ui import render_launch_link
    st.subheader(name)
    st.button('연결 다시 준비', key='hwcalc_refresh_launch', use_container_width=True)
    issued_at = time.time()
    url = prepared_new_tab_url(name, ids)
    if not url:
        st.error('연결을 준비하지 못했습니다. 다시 준비하거나 WORKSPACE에서 계산기를 다시 열어 주세요.')
        return
    render_launch_link(url, '새 탭으로 열기 ↗', issued_at=issued_at)

def clear_calculator_query():
    try:
        if 'calc' in st.query_params:
            del st.query_params['calc']
    except (AttributeError, KeyError, TypeError):
        pass


def open_calculator(name):
    st.session_state['hwcalc_open'] = name
    st.session_state['hwcalc_selected'] = name
    st.session_state['hwcalc_catalog_last'] = name


def back_to_catalog():
    st.session_state.pop('hwcalc_open', None)
    st.session_state.pop('hwcalc_selected', None)
    clear_calculator_query()
    st.session_state['hwcalc_catalog_restore'] = True


def save_query():
    st.session_state['hwcalc_catalog_query'] = st.session_state.get('hwcalc_search', '')


def set_query(query):
    st.session_state['hwcalc_catalog_query'] = query
    st.session_state['hwcalc_search'] = query


def set_group(group):
    st.session_state['hwcalc_catalog_group'] = group


def scroll_memory(last, restore):
    selector = '.st-key-' + card_key(last) if last else ''
    st.iframe('''<script>
    (() => {
      const w = window.parent, d = w.document, key = 'hw-calculator-list-position';
      const container = d.querySelector('[data-testid="stMain"]') || d.querySelector('section.main');
      if (!container) return;
      if (w.__hwCatalogClick) d.removeEventListener('click', w.__hwCatalogClick, true);
      w.__hwCatalogClick = e => {
        if (e.target.closest('[class*="st-key-hwcalc_card_"]')) {
          w.__hwOpenCalculator = true;
          try { w.sessionStorage.setItem(key, JSON.stringify({top:container.scrollTop, y:w.scrollY})); } catch (_) {}
        }
      };
      d.addEventListener('click', w.__hwCatalogClick, true);
      if (RESTORE) {
        let attempts = 0;
        const recover = () => {
          const card = d.querySelector(SELECTOR);
          if (!card && attempts++ < 30) { w.setTimeout(recover, 80); return; }
          let saved;
          try { saved = JSON.parse(w.sessionStorage.getItem(key)); } catch (_) {}
          if (d.activeElement && /INPUT|TEXTAREA/.test(d.activeElement.tagName)) return;
          if (saved) { container.scrollTop = Math.min(saved.top,container.scrollHeight-container.clientHeight); w.scrollTo(0, saved.y); }
          else if (card) card.scrollIntoView({block:'center'});
        };
        w.requestAnimationFrame(() => w.setTimeout(recover, 100));
      }
    })();
    </script>'''.replace('RESTORE', json.dumps(restore)).replace('SELECTOR', json.dumps(selector)), height=1)


def render_catalog(items, groups, implemented, *, tags=None, ids=None):
    from modules.shared import brand_ui as ui
    from modules.calculators.calculator_shell import _show_catalog
    ui.apply()
    tags = tags or {}
    st.session_state.setdefault('hwcalc_catalog_query', '')
    group = st.session_state.get('hwcalc_catalog_group', '전체')
    is_home = group == '전체'
    available = [(n,g,d) for n,(g,d) in items.items() if n in implemented]
    st.title('종합 계산기 센터' if is_home else group)
    st.caption('상담에 필요한 계산기를 빠르게 찾아보세요.' if is_home else f'{sum(g == group for _,g,_ in available)}개 계산기')
    if 'hwcalc_search' not in st.session_state:
        st.session_state['hwcalc_search'] = st.session_state['hwcalc_catalog_query']
    search, clear = st.columns([8,1])
    search.text_input('계산기 검색' if is_home else '이 분류에서 검색', key='hwcalc_search', on_change=save_query,
        placeholder='예: 노후 생활비, 자녀 증여, 보험료' if is_home else '이 분류의 계산기 이름 검색',label_visibility='collapsed')
    clear.button('초기화',on_click=set_query,args=('',),key='hwcalc_search_clear')
    if is_home:
        with st.expander('상담 목적별로 찾기'):
            for i,(label,q) in enumerate(PURPOSES):
                st.button(label,key=f'hwcalc_purpose_{i}',on_click=set_query,args=(q,),type='tertiary')
    query=st.session_state['hwcalc_catalog_query'].strip()
    found=[(n,g,d) for n,g,d in available if (is_home or g==group) and matches(n,g,d,tags.get(n,()),query)]
    if is_home and not query:
        st.subheader('업무별 계산기')
        with st.container(key='brand_grid_categories',horizontal=True):
            for i,g in enumerate(groups):
                from modules.calculators.hwarang_calculator_center import GROUPS
                purpose_index=list(GROUPS).index(g)
                count=sum(c==g for _,c,_ in available)
                if count:
                    ui.card(g, PURPOSES[purpose_index][0] if purpose_index<len(PURPOSES) else '상담에 필요한 수치를 확인하세요.',category_emoji(g),f'brand_tile_group_{i}',_show_catalog,(g,),badge=f'{count}개')
    else:
        if query: st.caption(f'검색 결과 {len(found)}개')
        with st.container(key='brand_grid_calculators',horizontal=True):
            for n,g,d in found:
                ui.card(n,d,category_emoji(g),card_key(n),open_calculator,(n,))
        if not found:
            st.info('일치하는 계산기가 없습니다. 검색어를 바꾸거나 전체 분류에서 찾아보세요.')
            st.button('전체 분류 보기',on_click=_show_catalog,key='hwcalc_empty_home')
    scroll_memory(st.session_state.get('hwcalc_catalog_last'),st.session_state.pop('hwcalc_catalog_restore',False))
