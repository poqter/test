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
    tags = tags or {}
    ids = ids or {}

    st.session_state.setdefault('hwcalc_catalog_query', st.session_state.get('hwcalc_search', ''))
    st.session_state.setdefault('hwcalc_catalog_group', st.session_state.get('hwcalc_group', '전체'))
    group = st.session_state['hwcalc_catalog_group']
    is_home = group == '전체'

    if is_home:
        st.markdown('#### 🔎 계산기 검색')
        st.caption('계산기 이름 또는 고객의 상황으로 검색하세요.')
        if 'hwcalc_search' not in st.session_state:
            st.session_state['hwcalc_search'] = st.session_state['hwcalc_catalog_query']
        search, clear = st.columns([8, 1])
        search.text_input(
            '계산기 이름 또는 상담 목적',
            key='hwcalc_search',
            on_change=save_query,
            placeholder='예: 노후 생활비, 자녀 증여, 보험료 부담',
            label_visibility='collapsed',
        )
        clear.button(
            '초기화',
            key='hwcalc_search_clear',
            on_click=set_query,
            args=('',),
            use_container_width=True,
        )
        with st.container(key='hwcalc_purposes', horizontal=True):
            for i, (label, purpose_query) in enumerate(PURPOSES):
                st.button(
                    purpose_label(label),
                    key=f'hwcalc_purpose_{i}',
                    on_click=set_query,
                    args=(purpose_query,),
                    type='tertiary',
                )
        query = st.session_state['hwcalc_catalog_query'].strip()
    else:
        # 업무 분류 화면은 탐색 결과에 집중합니다. 숨겨진 검색 상태를 적용하지 않습니다.
        query = ''

    found = [
        (n, g, d)
        for n, (g, d) in items.items()
        if n in implemented
        and (bool(query) or group == '전체' or group == g)
        and matches(n, g, d, tags.get(n, ()), query)
    ]

    if query:
        heading = '🔎 검색 결과'
        st.markdown('#### ' + heading)
        st.caption(f'{len(found)}개 결과')
    elif group == '전체':
        heading = '🧮 전체 계산기'
        st.markdown('#### ' + heading)
        st.caption(f'{len(found)}개')
    else:
        # A category page already has one clear heading. Keep the item count on
        # the same line and start the calculator cards immediately below it.
        heading = category_label(group) + ' 계산기'
        st.markdown(
            '<div class="hw-catalog-category-title"><span>' + escape(heading) + '</span>'
            '<b>' + str(len(found)) + '개</b></div>',
            unsafe_allow_html=True,
        )

    st.markdown('''<style>
    .hw-catalog-category-title{display:flex;align-items:center;gap:9px;margin:5px 0 13px;min-width:0}
    .hw-catalog-category-title span{font-size:20px;font-weight:700;line-height:1.4;color:#203a58;letter-spacing:-.025em;word-break:keep-all}
    .hw-catalog-category-title b{display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;min-height:25px;padding:2px 9px;border:1px solid #cbd9e7;border-radius:999px;background:#edf3f9;color:#426588;font-size:12px;font-weight:700;line-height:1}
    .st-key-hwcalc_search [data-baseweb="input"],
    .st-key-hwcalc_search [data-testid="stTextInput"] > div > div{
        background:#fff!important;
        border:2px solid #b7c6d6!important;
        border-radius:12px!important;
        box-shadow:0 1px 3px rgba(25,57,89,.08)!important;
        transition:border-color .16s ease,box-shadow .16s ease!important;
    }
    .st-key-hwcalc_search:hover [data-baseweb="input"],
    .st-key-hwcalc_search:hover [data-testid="stTextInput"] > div > div{
        border-color:#8faac3!important;
    }
    .st-key-hwcalc_search [data-baseweb="input"]:focus-within,
    .st-key-hwcalc_search [data-testid="stTextInput"] > div > div:focus-within{
        border-color:#4d7fab!important;
        box-shadow:0 0 0 3px rgba(77,127,171,.14)!important;
    }
    .st-key-hwcalc_search input{
        background:transparent!important;
        color:#203a58!important;
        min-height:44px!important;
        border:0!important;
        outline:0!important;
        box-shadow:none!important;
    }
    .st-key-hwcalc_search input::placeholder{color:#8395a8!important;opacity:1!important}
    .st-key-hwcalc_search_clear button{min-height:48px!important;border:1px solid #c9d6e3!important;border-radius:11px!important}
    [class*="st-key-hwcalc_card_"][data-testid="stVerticalBlock"]{background:#fff;border:1px solid #dce5ef;border-radius:14px;padding:20px;transition:border-color .18s,box-shadow .18s}
    [class*="st-key-hwcalc_card_"][data-testid="stVerticalBlock"]:hover{border-color:#9cb6d0;box-shadow:0 4px 14px #18395c0a}
    .hw-calc-card-copy{display:flex;align-items:flex-start;gap:12px;padding:5px 0}
    .hw-calc-card-icon{display:grid;place-items:center;flex-shrink:0;width:42px;height:42px;border-radius:12px;background:#eef3fa;font-size:24px}
    .hw-calc-card-title{font-size:17px;font-weight:700;color:#203a58;line-height:1.45;margin-bottom:6px;word-break:keep-all;overflow-wrap:anywhere}
    .hw-calc-card-summary{font-size:13px;line-height:1.65;color:#657b91;word-break:keep-all;overflow-wrap:anywhere}
    .hw-calc-card-core{font-size:12px;line-height:1.5;color:#426e98;margin-top:7px;word-break:keep-all;overflow-wrap:anywhere}
    [class*="st-key-hwcalc_actions_"][data-testid="stVerticalBlock"]{gap:8px!important;border-left:1px solid #edf1f6;padding-left:14px;justify-content:center}
    [class*="st-key-hwcalc_card_"] button,.hw-calc-new-tab{width:100%;min-height:42px!important;padding:9px 8px!important;border-radius:9px!important;font-size:12px!important;line-height:1.35!important;transform:none!important;box-shadow:none!important}
    [class*="st-key-hwcalc_card_"] [data-testid="stButton"] button{background:#e9f0f8!important;color:#214b76!important;border:1px solid #cbd9e7!important;justify-content:center!important;font-weight:650!important}
    [class*="st-key-hwcalc_card_"] [data-testid="stButton"] button:hover{background:#dfeaf6!important;border-color:#a9bfd5!important}
    [class*="st-key-hwcalc_card_"] button p{font-size:12px!important;white-space:nowrap!important}
    .hw-calc-new-tab{display:flex;align-items:center;justify-content:center;box-sizing:border-box;background:#fff!important;color:#365f87!important;border:1px solid #cbd9e7!important;text-decoration:none!important;font-weight:600!important;white-space:nowrap}
    .hw-calc-new-tab:hover{background:#f5f8fc!important;border-color:#9fb7cf!important;color:#214b76!important;text-decoration:none!important}
    [class*="st-key-hwcalc_actions_"] [data-testid="stMarkdownContainer"]{width:100%!important}
    [class*="st-key-hwcalc_actions_"] [data-testid="stMarkdownContainer"] p{margin:0!important;width:100%!important}
    .st-key-hwcalc_purposes{padding:2px 0 12px;border-bottom:1px solid #e4ebf2;margin-bottom:10px}
    .st-key-hwcalc_purposes button{font-size:12px!important;min-height:28px!important;padding:3px 9px!important;border-radius:16px!important;background:#edf2f7!important;color:#526982!important}
    .st-key-hwcalc_purposes button p{font-size:12px!important}
    [class*="st-key-hwcalc_card_"] button:focus-visible,.hw-calc-new-tab:focus-visible{outline:3px solid rgba(45,106,213,.28)!important;outline-offset:2px!important}
    @media(max-width:768px){
        [class*="st-key-hwcalc_card_"]>[data-testid="stHorizontalBlock"]{flex-direction:column!important}
        [class*="st-key-hwcalc_card_"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important}
        [class*="st-key-hwcalc_actions_"][data-testid="stVerticalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px!important;border-left:0;border-top:1px solid #edf1f6;padding:12px 0 0;justify-content:stretch}
        [class*="st-key-hwcalc_card_"] button,.hw-calc-new-tab{min-height:44px!important}
    }
    @media(max-width:480px){[class*="st-key-hwcalc_actions_"][data-testid="stVerticalBlock"]{grid-template-columns:1fr!important}}
    @media(prefers-reduced-motion:reduce){
        [class*="st-key-hwcalc_card_"]{transition:none!important}
        .st-key-hwcalc_search [data-baseweb="input"],.st-key-hwcalc_search [data-baseweb="base-input"]{transition:none!important}
    }
    </style>''', unsafe_allow_html=True)

    if query:
        q = normalize(query).removesuffix('계산기')
        def rank(item):
            n = normalize(item[0]).removesuffix('계산기')
            return 0 if n == q else 1 if n.startswith(q) or q in initials(n) else 2 if q in n else 3
        found.sort(key=rank)
        sections = [('이름 일치', [item for item in found if rank(item) < 2]),
                    ('관련 계산기', [item for item in found if rank(item) >= 2])]
    elif group == '전체':
        sections = [(category, [item for item in found if item[1] == category]) for category in groups]
    else:
        # The selected category is already named in the page heading above.
        # A second identical subheading only adds vertical space.
        sections = [(None, found)]

    for category, section_items in sections:
        subset = [(n, d) for n, g, d in section_items]
        if not subset:
            continue
        if category is not None:
            st.markdown('##### ' + (category if category in ('이름 일치', '관련 계산기') else category_label(category)))
        for start in range(0, len(subset), 2):
            cols = st.columns(2)
            for col, (name, description) in zip(cols, subset[start:start + 2]):
                summary = description.replace('계산 결과: ', '').split(' 적용 조건')[0]
                meta = profile(name)
                with col.container(key=card_key(name)):
                    copy, actions = st.columns([2.15, 1], gap='small', vertical_alignment='center')
                    icon = category_emoji(items[name][0])
                    copy.markdown(
                        f'<div class="hw-calc-card-copy"><span class="hw-calc-card-icon" aria-hidden="true">{icon}</span>'
                        f'<div><div class="hw-calc-card-title">{escape(name.removesuffix("계산기"))}</div>'
                        f'<div class="hw-calc-card-summary">{escape(summary)}</div>'
                        f'<div class="hw-calc-card-core">먼저 입력 · {escape(meta.get("core", "핵심 조건"))}</div></div></div>',
                        unsafe_allow_html=True,
                    )
                    with actions.container(key="hwcalc_actions_"+card_key(name)):
                        st.button('현재 화면에서 열기',key=card_key(name)+'_open_here',on_click=open_calculator,args=(name,),use_container_width=True)
                        if st.button('새 탭으로 열기 ↗', key=card_key(name)+'_prepare_tab', use_container_width=True):
                            open_new_tab(name, ids)
    if not found:
        st.info('일치하는 계산기가 없습니다. 다른 키워드를 입력해보세요.')
    last = st.session_state.get('hwcalc_catalog_last')
    if last:
        st.markdown(f'<style>.st-key-{card_key(last)}[data-testid="stVerticalBlock"]{{border-color:#5584b2!important;box-shadow:0 0 0 2px #bcd3ea60!important}}</style>', unsafe_allow_html=True)
    scroll_memory(last, st.session_state.pop('hwcalc_catalog_restore', False))
