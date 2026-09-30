"""Presentation-only money units; calculation engines continue to receive won."""
import hashlib
import re
from html import escape
from decimal import Decimal, ROUND_HALF_UP
import streamlit as st


def amount_words(won):
    n = int(Decimal(str(won)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if not n:
        return '0원'
    def block(v):
        out = ''
        for base, unit in ((1000,'천'),(100,'백'),(10,'십'),(1,'')):
            digit, v = divmod(v, base)
            if digit:
                out += ('' if digit == 1 and base > 1 else str(digit)) + unit
        return out
    parts = []
    for base, unit in ((10**12,'조'),(10**8,'억'),(10000,'만'),(1,'')):
        part, n = divmod(n, base)
        if part:
            parts.append((f'{part:,}' if base >= 10**8 else block(part)) + unit)
    return ' '.join(parts) + '원'


def uses_won_precision(label):
    """Keep unit-price inputs in won instead of converting them to manwon."""
    return any(word in label for word in ('주당', '액면가', '행사가액'))


def uses_decimal_manwon(label):
    """Allow 100-won precision for recurring insurance-premium inputs."""
    return any(word in label for word in ('월 보험료', '보험료 월납', '월납 보험료'))


def number_input(label, **kwargs):
    if not re.search(r'(?<!만)원\)', label):
        return st.number_input(label, **kwargs)
    # Per-unit values keep won precision. Monthly premiums use decimal manwon.
    if uses_won_precision(label):
        kwargs['step'] = 1
        kwargs['format'] = '%d'
        for option in ('value', 'min_value', 'max_value'):
            if option in kwargs and kwargs[option] is not None:
                kwargs[option] = int(kwargs[option])
        return st.number_input(label, **kwargs)
    old_key = kwargs.pop('key', None)
    base = old_key or 'jc_money_' + hashlib.sha256(label.encode()).hexdigest()[:12]
    decimal_manwon = uses_decimal_manwon(label)
    key = base + ('_manwon_decimal' if decimal_manwon else '_manwon_int')
    def rounded(value):
        raw = Decimal(str(value)) / 10000
        if decimal_manwon:
            return float(raw.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        return int(raw.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    for option in ('value', 'min_value', 'max_value', 'step'):
        if option in kwargs and kwargs[option] is not None:
            raw = Decimal(str(kwargs[option])) / 10000
            if option == 'min_value':
                from decimal import ROUND_CEILING
                kwargs[option] = int(raw.to_integral_value(rounding=ROUND_CEILING))
            elif option == 'max_value':
                from decimal import ROUND_FLOOR
                kwargs[option] = int(raw.to_integral_value(rounding=ROUND_FLOOR))
            else: kwargs[option] = rounded(kwargs[option])
    if decimal_manwon:
        kwargs['step'] = 0.01
        kwargs['format'] = '%.12g'
    else:
        kwargs['step'] = max(1,kwargs.get('step',1))
        kwargs['format'] = '%d'
    if key not in st.session_state:
        legacy_keys = (base + '_manwon_decimal', base + '_manwon_int', base + '_manwon')
        for legacy_key in legacy_keys:
            if legacy_key in st.session_state:
                legacy_value = st.session_state[legacy_key]
                if legacy_key.endswith('_manwon_int') or legacy_key.endswith('_manwon'):
                    st.session_state[key] = float(legacy_value) if decimal_manwon else int(legacy_value)
                else:
                    st.session_state[key] = float(legacy_value) if decimal_manwon else int(Decimal(str(legacy_value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                break
        else:
            if old_key and old_key in st.session_state:
                st.session_state[key] = rounded(st.session_state[old_key])
    v = st.number_input(label.replace('원)', '만원)'), key=key, **kwargs)
    won = int((Decimal(str(v)) * 10000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    st.markdown(f'<div data-hw-money-label="{escape(label.replace("원)", "만원)"), quote=True)}" style="font-size:12px;color:#426e98;text-align:right;margin-top:-8px">{amount_words(won)}</div>', unsafe_allow_html=True)
    return won


def input_panels(key):
    st.markdown('''<style>
    [class*="st-key-hw_calc_"] [data-testid="stNumberInput"] input {color:#203952!important;font-size:17px!important}
    [class*="st-key-hw_calc_"] [data-testid="stNumberInput"] {margin-bottom:0}
    [class*="st-key-hw_calc_"] [data-testid="stCaptionContainer"] {color:#426e98!important}
    </style>''', unsafe_allow_html=True)
    st.iframe("""<script>
    (()=>{const w=window.parent,d=w.document;
      if(w.__hwMoneyInput)d.removeEventListener('input',w.__hwMoneyInput,true);
      w.__hwMoneyInput=e=>{const el=e.target;if(el.tagName!=='INPUT')return;
        const label=el.getAttribute('aria-label');
        const node=[...d.querySelectorAll('[data-hw-money-label]')].find(n=>n.dataset.hwMoneyLabel===label);
        if(!node)return;
        const s=el.value.replaceAll(',','').trim();const value=Number(s);
        if(!s){node.textContent='금액을 입력해주세요';return;}
        if(!Number.isFinite(value)||value<0){node.textContent='금액을 확인해주세요';return;}
        let n=Math.round(value*10000),out=[];
        const block=x=>{let t='';for(const [v,u] of [[1000,'천'],[100,'백'],[10,'십'],[1,'']]){const a=Math.floor(x/v);if(a)t+=(a===1&&v>1?'':a)+u;x%=v;}return t;};
        for(const [v,u] of [[1e12,'조'],[1e8,'억'],[1e4,'만'],[1,'']]){const a=Math.floor(n/v);if(a)out.push((v>=1e8?a.toLocaleString('ko-KR'):block(a))+u);n%=v;}
        node.textContent=(out.length?out.join(' '):'0')+'원';
      };d.addEventListener('input',w.__hwMoneyInput,true);
    })();
    </script>""",height=1)
    from contextlib import contextmanager
    with st.container(key='hw_calc_'+key):
        left,right=st.columns([1.25,1],gap='large')
        inputs=left.container(border=True, key='hw_calc_input_'+key)
        results=right.container(border=True, key='hw_calc_result_'+key)
        with results:
            hint=st.empty()
            hint.info('🧮 입력 조건을 확인한 뒤 계산하기를 눌러주세요.')
    @contextmanager
    def result_context():
        hint.empty()
        with results: yield
    return inputs,result_context()


def _primary_metric_index(items, preferred_labels=()):
    """Select an audited primary label, then fall back to the first monetary value."""
    labels = [label for label, _value in items]
    for preferred in preferred_labels or ():
        if preferred in labels:
            return labels.index(preferred)
    for index, (_label, value) in enumerate(items):
        text = str(value).replace(" ", "")
        if any(unit in text for unit in ("조원", "억원", "만원", "원")):
            return index
    return 0


def render_metrics(display, prefix, preferred_labels=()):
    """Render one unmistakable representative result and compact support values."""
    items = list(display.items())
    if not items:
        return
    primary_index = _primary_metric_index(items, preferred_labels)
    primary_label, primary_value = items[primary_index]
    with st.container(key=prefix + '_hero_result'):
        st.markdown('<div class="hw-primary-result-kicker">✨ 대표 계산 결과</div>', unsafe_allow_html=True)
        st.metric(primary_label, primary_value)
    support_index = 0
    for index, (label, value) in enumerate(items):
        if index == primary_index:
            continue
        support_index += 1
        with st.container(key=prefix + '_support_result_' + str(support_index)):
            st.metric(label, value)


def jump_to_result(submitted, panel):
    # Only a successful explicit calculation may scroll. Editing/exporting does not.
    if not submitted:
        return
    import json
    selector = '.st-key-hw_calc_result_' + panel
    st.iframe("""<script>(()=>{const w=window.parent,d=w.document;
    const node=d.querySelector(SELECTOR);if(!node)return;
    const r=node.getBoundingClientRect();
    if(r.top<0||r.top>w.innerHeight*.65)node.scrollIntoView({block:'start',
    behavior:w.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    })();</script>""".replace('SELECTOR',json.dumps(selector)),height=1)
