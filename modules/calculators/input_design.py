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


def number_input(label, **kwargs):
    if not re.search(r'(?<!만)원\)', label):
        return st.number_input(label, **kwargs)
    old_key = kwargs.pop('key', None)
    base = old_key or 'jc_money_' + hashlib.sha256(label.encode()).hexdigest()[:12]
    key = base + '_manwon_int'
    def rounded(value):
        return int((Decimal(str(value))/10000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
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
    kwargs['step'] = max(1,kwargs.get('step',1))
    kwargs['format'] = '%d'
    if key not in st.session_state:
        if base + '_manwon' in st.session_state:
            st.session_state[key] = int(Decimal(str(st.session_state[base+'_manwon'])).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        elif old_key and old_key in st.session_state:
            st.session_state[key] = rounded(st.session_state[old_key])
    v = st.number_input(label.replace('원)', '만원)'), key=key, **kwargs)
    won = int(v) * 10000
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
        inputs=left.container(border=True)
        results=right.container(border=True)
        with results:
            hint=st.empty()
            hint.info('입력 조건을 확인한 뒤 계산하기를 눌러주세요.')
    @contextmanager
    def result_context():
        hint.empty()
        with results: yield
    return inputs,result_context()
