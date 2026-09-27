"""Calculator discovery UI. Keeps navigation state separate from widget state."""
import hashlib
import json
import re
import streamlit as st

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

def open_calculator(name):
    st.session_state['jc_open'] = name
    st.session_state['jc_selected'] = name
    st.session_state['jc_catalog_last'] = name


def back_to_catalog():
    st.session_state.pop('jc_open', None)
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
          if (saved) { container.scrollTop = saved.top; w.scrollTo(0, saved.y); }
          else if (card) card.scrollIntoView({block:'center'});
          const button = card && card.querySelector('button');
          if (button) button.focus({preventScroll:true});
        };
        w.requestAnimationFrame(() => w.setTimeout(recover, 100));
      }
    })();
    </script>'''.replace('RESTORE', json.dumps(restore)).replace('SELECTOR', json.dumps(selector)), height=1)


def render_catalog(items, groups, implemented):
    st.markdown('### 어떤 상담을 준비하시나요?')
    st.caption('계산기 이름을 몰라도, 고객의 상황으로 찾아보세요.')
    st.session_state.setdefault('jc_catalog_query', st.session_state.get('jc_search', ''))
    st.session_state.setdefault('jc_catalog_group', st.session_state.get('jc_group', '전체'))
    if 'jc_search' not in st.session_state:
        st.session_state['jc_search'] = st.session_state['jc_catalog_query']
    search, clear = st.columns([8, 1])
    search.text_input('계산기 이름 또는 상담 목적', key='jc_search', on_change=save_query,
                      placeholder='예: 노후 생활비, 자녀 증여, 보험료 부담', label_visibility='collapsed')
    clear.button('초기화', key='jc_search_clear', on_click=set_query, args=('',), use_container_width=True)
    with st.container(key='jc_purposes'):
        cols = st.columns(3)
        for i, (label, query) in enumerate(PURPOSES):
            cols[i % 3].button(label, key=f'jc_purpose_{i}', on_click=set_query, args=(query,), use_container_width=True,
                                type='primary' if st.session_state['jc_catalog_query'] == query else 'secondary')
    group = st.session_state['jc_catalog_group']
    with st.container(key='jc_categories'):
        cols = st.columns(4)
        for i, category in enumerate(('전체', *groups)):
            cols[i % 4].button(category.split(' · ')[-1], key=f'jc_category_{i}', on_click=set_group, args=(category,),
                               use_container_width=True, type='primary' if group == category else 'secondary')
    query = st.session_state['jc_catalog_query']
    found = [(n, g, d) for n, (g, d) in items.items() if n in implemented
             and (group == '전체' or group == g) and matches(n, g, d, query)]
    st.markdown('#### ' + ('검색 결과' if query else group + ' 계산기'))
    st.caption(f'{len(found)}개 · 카드를 누르면 바로 열립니다.')
    st.markdown('''<style>
    .st-key-jc_categories {padding:12px 0;border-bottom:1px solid #dce5ef;margin-bottom:10px}
    [class*="st-key-jc_card_"] button{min-height:158px!important;background:#fff!important;border:1px solid #dce5ef!important;border-radius:14px!important;padding:20px!important;text-align:left!important;justify-content:flex-start!important;color:#223b56!important;transition:box-shadow .18s,border-color .18s!important;transform:none!important}
    [class*="st-key-jc_card_"] button:hover{border-color:#7e9ebf!important;box-shadow:0 5px 16px #25456912!important;transform:none!important}
    [class*="st-key-jc_card_"] button p{font-size:14px!important;line-height:1.65!important;text-align:left!important}
    [class*="st-key-jc_card_"] button strong{font-size:17px!important;color:#1d3653!important}
    .st-key-jc_purposes button{font-size:13px!important;border-radius:20px!important}
    @media(prefers-reduced-motion:reduce){[class*="st-key-jc_card_"] button{transition:none!important}}
    </style>''', unsafe_allow_html=True)
    for gi, category in enumerate(groups):
        subset = [(n, d) for n, g, d in found if g == category]
        if not subset:
            continue
        st.markdown('##### ' + category)
        for start in range(0, len(subset), 3):
            cols = st.columns(3)
            for col, (name, description) in zip(cols, subset[start:start + 3]):
                summary = description.replace('계산 결과: ', '').split(' 적용 조건')[0]
                label = f"{('🧾','🌿','🛡️','📈','🏢','📑')[gi]} **{name.removesuffix('계산기')}**\n\n{summary}　↗"
                col.button(label, key=card_key(name), on_click=open_calculator, args=(name,), use_container_width=True)
    if not found:
        st.info('일치하는 계산기가 없습니다. 다른 키워드를 입력하거나 분류를 전체로 바꿔보세요.')
    st.divider()
    st.button('보험 기본·생활자금 계산 →', key=card_key('__basic__'), on_click=open_calculator, args=('__basic__',))
    last = st.session_state.get('jc_catalog_last')
    if last:
        st.markdown(f'<style>.st-key-{card_key(last)} button{{border-color:#5584b2!important;box-shadow:0 0 0 2px #bcd3ea60!important}}</style>', unsafe_allow_html=True)
    scroll_memory(last, st.session_state.pop('jc_catalog_restore', False))
