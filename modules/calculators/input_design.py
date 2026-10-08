"""Presentation-only money units; calculation engines continue to receive won."""
import hashlib
import re
from html import escape
from decimal import Decimal, ROUND_HALF_UP
import streamlit as st


def amount_words(won):
    """Readable Korean large units, preserving sign and every whole won."""
    from modules.shared.numeric import integer_won
    number = integer_won(won)
    sign = "-" if number < 0 else ""
    remainder = abs(number)
    if not remainder:
        return "0원"
    parts = []
    for scale, unit in ((10**12, "조"), (10**8, "억"), (10**4, "만"), (1, "")):
        block, remainder = divmod(remainder, scale)
        if block:
            parts.append(f"{block:,}{unit}")
    return sign + " ".join(parts) + "원"


def uses_won_precision(label):
    """Confirmed values and unit prices are never rounded to display units."""
    return any(word in label for word in (
        "주당", "1주당", "액면가", "행사가", "확인액", "확정", "실제", "기납부",
        "세액", "소득공제", "세액공제", "과세표준", "보험료", "납부액", "취득가",
        "양도가", "장부가", "급여", "보수", "신고", "배당", "매출", "수입금액", "필요경비",
    ))


def uses_decimal_manwon(label):
    # Compatibility predicate: premium fields now use exact integer won.
    return False


def money_policy(label, explicit=None):
    if explicit is not None:
        if explicit not in ("exact_won", "plan_manwon"):
            raise ValueError("지원하지 않는 금액 입력 정책입니다.")
        return explicit
    return "exact_won" if uses_won_precision(label) else "plan_manwon"


def money_widget_key(base):
    return base + "_money_v3"


def _from_display(value, policy):
    from modules.shared.numeric import decimal_number, integer_won
    if value is None:
        return None
    scale = 1 if policy == "exact_won" else 10_000
    return integer_won(decimal_number(value) * scale)


def read_money_state(base, label, default=None, *, policy=None):
    """Read canonical won including compatible earlier-session widget values."""
    policy = money_policy(label, policy)
    key = money_widget_key(base)
    meta = st.session_state.get("hw.money_policy." + base, policy)
    if key in st.session_state:
        from modules.shared.numeric import NumericInputError
        try:
            return _from_display(st.session_state[key], meta)
        except NumericInputError:
            # Keep the raw widget value for correction. render_input below
            # shows its validation error; a snapshot must not crash first.
            return None
    stored = st.session_state.get("hw.money_values", {})
    if base in stored:
        return stored[base]
    # An explicitly transferred won value has precedence over old display keys.
    if base in st.session_state:
        return _from_display(st.session_state[base], "exact_won")
    for suffix in ("_manwon_decimal", "_manwon_int", "_manwon"):
        if base + suffix in st.session_state:
            return _from_display(st.session_state[base + suffix], "plan_manwon")
    return default


def set_money_state(base, label, won, *, policy=None):
    from modules.shared.numeric import integer_won
    policy = money_policy(label, policy)
    value = integer_won(won, allow_empty=True)
    scale = 1 if policy == "exact_won" else 10_000
    shown = None if value is None else (value if scale == 1 else float(Decimal(value) / scale))
    st.session_state[money_widget_key(base)] = shown
    st.session_state["hw.money_policy." + base] = policy
    st.session_state.setdefault("hw.money_values", {})[base] = value
    for suffix in ("", "_manwon_decimal", "_manwon_int", "_manwon"):
        st.session_state.pop(base + suffix, None)


def number_input(label, **kwargs):
    """Keep display units separate from values, never quantize a customer value.

    Exact fields: integer won. Plan fields: convenient manwon with a 1-manwon
    stepping interval; manually entered fractions retain up to 1 won. %.12g
    hides trailing zeroes without changing the number being calculated.
    """
    policy = kwargs.pop("money_policy", None)
    if not re.search(r'(?<!만)원\)', label):
        # Streamlit requires value/min/max/step to have matching numeric types.
        numeric = [kwargs.get(k) for k in ("value", "min_value", "max_value", "step")]
        as_float = any(isinstance(v, (float, Decimal)) for v in numeric if v is not None)
        if as_float:
            for key in ("value", "min_value", "max_value", "step"):
                if key in kwargs and kwargs[key] is not None and kwargs[key] != "min":
                    kwargs[key] = float(kwargs[key])
            kwargs.setdefault("format", "%.12g")
        return st.number_input(label, **kwargs)
    from modules.shared.numeric import integer_won, NumericInputError
    policy = money_policy(label, policy)
    base = kwargs.pop("key", None) or "hwcalc_money_" + hashlib.sha256(label.encode()).hexdigest()[:12]
    scale = 1 if policy == "exact_won" else 10_000
    key = money_widget_key(base)
    default = kwargs.get("value", kwargs.get("min_value", 0))
    initial = read_money_state(base, label, default, policy=policy)
    if key not in st.session_state or st.session_state.get("hw.money_policy." + base, policy) != policy:
        set_money_state(base, label, initial, policy=policy)
    st.session_state["hw.money_policy." + base] = policy
    for option in ("value", "min_value", "max_value"):
        if option in kwargs and kwargs[option] is not None:
            raw = integer_won(kwargs[option])
            kwargs[option] = raw if scale == 1 else float(Decimal(raw) / scale)
    if scale == 1:
        kwargs["step"] = 1
        kwargs["format"] = "%d"
    else:
        kwargs["step"] = 1.0
        kwargs["format"] = "%.12g"
    # The session value is the single source of the widget default.
    kwargs.pop("value", None)
    shown_label = label if scale == 1 else label.replace("원)", "만원)")
    v = st.number_input(shown_label, key=key, **kwargs)
    try:
        won = _from_display(v, policy)
    except NumericInputError as exc:
        st.error(str(exc))
        won = None
    st.session_state.setdefault("hw.money_values", {})[base] = won
    hint = "입력 필요" if won is None else amount_words(won)
    st.markdown(f'<div class="hw-money-hint">{escape(hint)}</div>', unsafe_allow_html=True)
    return won


def input_panels(key):
    st.markdown('''<style>
    [class*="st-key-hw_calc_"] [data-testid="stNumberInput"] input {color:#203952!important;font-size:17px!important}
    [class*="st-key-hw_calc_"] [data-testid="stNumberInput"] {margin-bottom:0}
    [class*="st-key-hw_calc_"] [data-testid="stCaptionContainer"] {color:#426e98!important}
    .hw-money-hint{font-size:12px;color:#426e98;text-align:right;margin-top:-6px}
    </style>''', unsafe_allow_html=True)
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
