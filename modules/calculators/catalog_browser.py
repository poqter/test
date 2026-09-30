"""Calculator discovery UI. Keeps navigation state separate from widget state."""
import hashlib
import json
import re
from html import escape
from urllib.parse import quote
import streamlit as st
from modules.calculators.ux_profiles import profile
from modules.calculators.visuals import category_emoji, category_label, purpose_label

PURPOSES = (
    ('보험료가 부담돼요', '보험료 부담'), ('노후를 준비해요', '노후 생활비'),
    ('자녀에게 물려줘요', '자녀 증여'), ('치료비가 걱정돼요', '치료비'),
    ('대표 보수를 정해요', '급여 배당'), ('목돈을 모으고 싶어요', '목돈 저축'),
)
RULES = (
    ('보험료 부담 비싸 줄이고 적정', ('적정보험료', '정기·종신', '기회비용')),
    ('노후 생활비 은퇴 연금', ('은퇴', '연금')),
    ('자녀 증여 물려 상속', ('증여', '상속', '승계')),
    ('치료비 암 뇌 심장 질병 아프', ('중대질병', '의료비', '간병', '자녀보험')),
    ('급여 배당 대표 보수 월급', ('급여vs배당', '근로소득', '4대보험')),
    ('목돈 저축 모으', ('목표자금', '복리', '미래가치', '투자수익', '수익률')),
    ('퇴직 퇴사', ('퇴직', '은퇴크레바스')),
    ('집 매매 팔 부동산', ('양도', '주택')),
    ('가지급 빌린', ('가지급', '인정이자')),
)

def normalize(text):
    return re.sub(r'[\s·.,?]', '', text.casefold())

def initials(text):
    return ''.join('ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'[(ord(c)-44032)//588]
                   if 44032 <= ord(c) < 55204 else c for c in text)

def matches(name, group, description, query):
    q = normalize(query)
    if not q:
        return True
    if q in normalize(name + ' ' + group + ' ' + description) or q in initials(normalize(name)):
        return True
    return any(any(k in q for k in keys.split()) and any(n in name for n in names)
               for keys, names in RULES)

def card_key(name):
    return 'jc_card_' + hashlib.sha256(name.encode()).hexdigest()[:12]


def calculator_deep_link(name):
    # Relative URL keeps the link valid for production, test and local Calculator apps.
    return '?calc=' + quote(name, safe='')


def clear_calculator_query():
    try:
        if 'calc' in st.query_params:
            del st.query_params['calc']
    except (AttributeError, KeyError, TypeError):
        pass


def open_calculator(name):
    st.session_state['jc_open'] = name
    st.session_state['jc_selected'] = name
    st.session_state['jc_catalog_last'] = name


def back_to_catalog():
    st.session_state.pop('jc_open', None)
    st.session_state.pop('jc_selected', None)
    clear_calculator_query()
    st.session_state['jc_catalog_restore'] = True


def save_query():
    st.session_state['jc_catalog_query'] = st.session_state.get('jc_search', '')


def set_query(query):
    st.session_state['jc_catalog_query'] = query
    st.session_state['jc_search'] = query
    st.session_state['jc_catalog_group'] = '전체'


def set_group(group):
    st.session_state['jc_catalog_group'] = group


def scroll_memory(last, restore):
    # One listener per Streamlit document, removed/replaced on each catalog render.
    # Session storage holds only an interface position, never customer inputs.
    selector = '.st-key-' + card_key(last) if last else ''
    st.iframe('''<script>
    (() => {
      const w = window.parent, d = w.document, key = 'hw-calculator-list-position';
      const container = d.querySelector('[data-testid="stMain"]') || d.querySelector('section.main');
      if (!container) return;
      if (w.__hwCatalogClick) d.removeEventListener('click', w.__hwCatalogClick, true);
      w.__hwCatalogClick = e => {
        if (e.target.closest('[class*="st-key-jc_card_"]')) {
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
          // Restore position without taking focus away from search or keyboard navigation.
        };
        w.requestAnimationFrame(() => w.setTimeout(recover, 100));
      }
    })();
    </script>'''.replace('RESTORE', json.dumps(restore)).replace('SELECTOR', json.dumps(selector)), height=1)


def render_catalog(items, groups, implemented):
    st.markdown('#### 🔎 계산기 검색')
    st.caption('계산기 이름 또는 고객의 상황으로 검색하세요.')
    st.session_state.setdefault('jc_catalog_query', st.session_state.get('jc_search', ''))
    st.session_state.setdefault('jc_catalog_group', st.session_state.get('jc_group', '전체'))
    if 'jc_search' not in st.session_state:
        st.session_state['jc_search'] = st.session_state['jc_catalog_query']
    search, clear = st.columns([8, 1])
    search.text_input('계산기 이름 또는 상담 목적', key='jc_search', on_change=save_query,
                      placeholder='예: 노후 생활비, 자녀 증여, 보험료 부담', label_visibility='collapsed')
    clear.button('초기화', key='jc_search_clear', on_click=set_query, args=('',), use_container_width=True)
    with st.container(key='jc_purposes', horizontal=True):
        for i, (label, query) in enumerate(PURPOSES):
            st.button(purpose_label(label), key=f'jc_purpose_{i}', on_click=set_query, args=(query,),
                      type='tertiary')
    st.caption('🗂️ 업무 분류')
    group = st.session_state['jc_catalog_group']
    with st.container(key='jc_categories', horizontal=True):
        for i, category in enumerate(('전체', *groups)):
            st.button(category_label(category), key=f'jc_category_{i}', on_click=set_group, args=(category,),
                      type='primary' if group == category else 'secondary')
    query = st.session_state['jc_catalog_query']
    found = [(n, g, d) for n, (g, d) in items.items() if n in implemented
             and (group == '전체' or group == g) and matches(n, g, d, query)]
    st.markdown('#### ' + ('🔎 검색 결과' if query else category_label(group) + ' 계산기'))
    st.caption(f'{len(found)}개 결과')
    st.markdown('''<style>
    .st-key-jc_search [data-baseweb="input"]{
        background:#fff!important;border:2px solid #b7c6d6!important;border-radius:12px!important;
        box-shadow:0 1px 2px rgba(25,57,89,.05)!important;transition:border-color .16s,box-shadow .16s
    }
    .st-key-jc_search [data-baseweb="input"]:focus-within{
        border-color:#4d7fab!important;box-shadow:0 0 0 3px rgba(77,127,171,.14)!important
    }
    .st-key-jc_search input{background:transparent!important;color:#203a58!important;min-height:44px!important}
    .st-key-jc_search input::placeholder{color:#8395a8!important;opacity:1!important}
    .st-key-jc_search_clear button{min-height:48px!important;border:1px solid #c9d6e3!important;border-radius:11px!important}
    .st-key-jc_categories{padding:12px 0;border-bottom:1px solid #dce5ef;margin-bottom:10px}
    [class*="st-key-jc_card_"][data-testid="stVerticalBlock"]{background:#fff;border:1px solid #dce5ef;border-radius:14px;padding:20px;transition:border-color .18s,box-shadow .18s}
    [class*="st-key-jc_card_"][data-testid="stVerticalBlock"]:hover{border-color:#9cb6d0;box-shadow:0 4px 14px #18395c0a}
    .hw-calc-card-copy{display:flex;align-items:flex-start;gap:12px;padding:5px 0}
    .hw-calc-card-icon{display:grid;place-items:center;flex-shrink:0;width:42px;height:42px;border-radius:12px;background:#eef3fa;font-size:24px}
    .hw-calc-card-title{font-size:17px;font-weight:700;color:#203a58;line-height:1.45;margin-bottom:6px;word-break:keep-all;overflow-wrap:anywhere}
    .hw-calc-card-summary{font-size:13px;line-height:1.65;color:#657b91;word-break:keep-all;overflow-wrap:anywhere}
    .hw-calc-card-core{font-size:12px;line-height:1.5;color:#426e98;margin-top:7px;word-break:keep-all;overflow-wrap:anywhere}
    [class*="st-key-jc_actions_"][data-testid="stVerticalBlock"]{gap:8px!important;border-left:1px solid #edf1f6;padding-left:14px;justify-content:center}
    [class*="st-key-jc_card_"] button,
    .hw-calc-new-tab{width:100%;min-height:42px!important;padding:9px 8px!important;border-radius:9px!important;font-size:12px!important;line-height:1.35!important;transform:none!important;box-shadow:none!important}
    [class*="st-key-jc_card_"] [data-testid="stButton"] button{background:#e9f0f8!important;color:#214b76!important;border:1px solid #cbd9e7!important;justify-content:center!important;font-weight:650!important}
    [class*="st-key-jc_card_"] [data-testid="stButton"] button:hover{background:#dfeaf6!important;border-color:#a9bfd5!important}
    [class*="st-key-jc_card_"] button p{font-size:12px!important;white-space:nowrap!important}
    .hw-calc-new-tab{display:flex;align-items:center;justify-content:center;box-sizing:border-box;background:#fff!important;color:#365f87!important;border:1px solid #cbd9e7!important;text-decoration:none!important;font-weight:600!important;white-space:nowrap}
    .hw-calc-new-tab:hover{background:#f5f8fc!important;border-color:#9fb7cf!important;color:#214b76!important;text-decoration:none!important}
    [class*="st-key-jc_actions_"] [data-testid="stMarkdownContainer"]{width:100%!important}
    [class*="st-key-jc_actions_"] [data-testid="stMarkdownContainer"] p{margin:0!important;width:100%!important}
    .st-key-jc_purposes button{font-size:12px!important;min-height:28px!important;padding:3px 9px!important;border-radius:16px!important;background:#edf2f7!important;color:#526982!important}
    .st-key-jc_purposes button p{font-size:12px!important}
    .st-key-jc_categories button{min-height:42px!important;font-weight:650!important}
    @media(max-width:768px){
        [class*="st-key-jc_card_"]>[data-testid="stHorizontalBlock"]{flex-direction:column!important}
        [class*="st-key-jc_card_"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important}
        [class*="st-key-jc_actions_"][data-testid="stVerticalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px!important;border-left:0;border-top:1px solid #edf1f6;padding:12px 0 0;justify-content:stretch}
        [class*="st-key-jc_card_"] button,.hw-calc-new-tab{min-height:44px!important}
    }
    @media(max-width:480px){[class*="st-key-jc_actions_"][data-testid="stVerticalBlock"]{grid-template-columns:1fr!important}}
    @media(prefers-reduced-motion:reduce){[class*="st-key-jc_card_"]{transition:none!important}.st-key-jc_search [data-baseweb="input"]{transition:none!important}}
    </style>''', unsafe_allow_html=True)
    if query:
        q = normalize(query).removesuffix('계산기')
        def rank(item):
            n = normalize(item[0]).removesuffix('계산기')
            return 0 if n == q else 1 if n.startswith(q) or q in initials(n) else 2 if q in n else 3
        found.sort(key=rank)
        sections = [('이름 일치', [item for item in found if rank(item) < 2]),
                    ('관련 계산기', [item for item in found if rank(item) >= 2])]
    else:
        sections = [(category, [item for item in found if item[1] == category]) for category in groups]
    for category, section_items in sections:
        subset = [(n, d) for n, g, d in section_items]
        if not subset:
            continue
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
                    with actions.container(key="jc_actions_"+card_key(name)):
                        st.button(
                            '현재 화면에서 열기',
                            key=card_key(name)+'_open_here',
                            on_click=open_calculator,
                            args=(name,),
                            use_container_width=True,
                        )
                        st.markdown(
                            f'<a class="hw-calc-new-tab" href="{calculator_deep_link(name)}" '
                            'target="_blank" rel="noopener noreferrer">새 탭으로 열기 ↗</a>',
                            unsafe_allow_html=True,
                        )
    if not found:
        st.info('일치하는 계산기가 없습니다. 다른 키워드를 입력하거나 분류를 전체로 바꿔보세요.')
    st.divider()
    st.button('🧮 보험 기본·생활자금 계산 →', key=card_key('__basic__'), on_click=open_calculator, args=('__basic__',))
    last = st.session_state.get('jc_catalog_last')
    if last:
        st.markdown(f'<style>.st-key-{card_key(last)}[data-testid="stVerticalBlock"]{{border-color:#5584b2!important;box-shadow:0 0 0 2px #bcd3ea60!important}}</style>', unsafe_allow_html=True)
    scroll_memory(last, st.session_state.pop('jc_catalog_restore', False))
