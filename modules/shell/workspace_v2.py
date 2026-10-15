"""Single home and sidebar implementation for the Stage 2 framework."""
from __future__ import annotations

import html
import time
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import streamlit as st

from modules.shell.app_registry import APP_BY_ID, SEARCH_ALIASES, AppSpec
from modules.resources.insurer_portal import render_home_quick_search
from modules.shared.external_apps import external_app_url
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService, SupabaseConfig

_ICONS = {
    "family": '<svg viewBox="0 0 24 24"><circle cx="9" cy="7" r="3"/><circle cx="17" cy="8" r="2.5"/><path d="M3 21v-2a6 6 0 0 1 12 0v2M16 14a5 5 0 0 1 5 5v2"/></svg>',
    "coins": '<svg viewBox="0 0 24 24"><ellipse cx="10" cy="5" rx="7" ry="3"/><path d="M3 5v5c0 4 14 4 14 0V5M3 10v5c0 2 4 3 7 3M3 15v3c0 2 4 3 7 3"/><circle cx="17" cy="17" r="4"/><path d="M17 15v4"/></svg>',
    "consultation": '<svg viewBox="0 0 24 24"><path d="M5 4h14v12H9l-4 4z"/><path d="M8 8h8M8 12h5"/></svg>',
    "calculator": '<svg viewBox="0 0 24 24"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h2M12 11h2M16 11h1M8 15h2M12 15h2M16 15h1"/></svg>',
    "analysis": '<svg viewBox="0 0 24 24"><path d="M12 3l8 3v5c0 5-3 8-8 10-5-2-8-5-8-10V6z"/><path d="m8.5 11.5 2.5 2.5 4.5-5"/></svg>',
    "materials": '<svg viewBox="0 0 24 24"><path d="M7 3h10v18H7z"/><path d="M10 8h4M9 12h6M9 16h6"/></svg>',
    "education": '<svg viewBox="0 0 24 24"><path d="M3 6l9-3 9 3-9 3z"/><path d="M6 8v6c3 2 9 2 12 0V8M21 6v8"/></svg>',
    "official": '<svg viewBox="0 0 24 24"><rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 21v-5h6v5M8 7h2m4 0h2M8 11h2m4 0h2"/></svg>',
    "performance": '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V6M16 20V3M22 20H2"/></svg>',
    "compare": '<svg viewBox="0 0 24 24"><path d="M7 5h13M17 2l3 3-3 3M17 19H4M7 16l-3 3 3 3"/></svg>',
    "remodeling": '<svg viewBox="0 0 24 24"><path d="M20 9a8 8 0 0 0-14-4L3 8m0-5v5h5M4 15a8 8 0 0 0 14 4l3-3m0 5v-5h-5"/></svg>',
    "tax": '<svg viewBox="0 0 24 24"><path d="M6 3h12v18H6zM9 8h6M9 12h2M13 12h2M9 16h6"/></svg>',
    "claim": '<svg viewBox="0 0 24 24"><rect x="5" y="4" width="14" height="17" rx="2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="m8 12 2.5 2.5 5-5M8 18h8"/></svg>',
    "medical": '<svg viewBox="0 0 24 24"><path d="M5 3v7a5 5 0 0 0 10 0V3M8 3v6a2 2 0 0 0 4 0V3M10 15v2a4 4 0 0 0 8 0v-1"/><circle cx="18" cy="13" r="3"/></svg>',
}






# Tickets are prepared only after an explicit app-open request. Background page
# rendering must not leave an already-expired, one-time URL on the screen.
_EXTERNAL_LAUNCH_CACHE_SECONDS = 45.0


def _external_launch_context(app: AppSpec) -> tuple[str, str, str] | None:
    """Read app configuration and the current permission gate without an RPC."""
    if not app.external_app_key or ("ws_allowed_ids" in st.session_state and app.id not in st.session_state["ws_allowed_ids"]):
        return None
    target = external_app_url(app.external_app_key)
    target_app = "academy" if app.id == "academy" else "calculator" if app.id == "quick_calculators" else ""
    state = st.session_state.get("hwarang_auth") or {}
    profile = state.get("profile") or {}
    uid = str(profile.get("id") or "")
    app_access = st.session_state.get("hw_app_access") or {}
    if not (target and uid and target_app and app_access.get(target_app, False)):
        return None
    return target_app, uid, target


def _external_launch_url(app: AppSpec, *, fresh: bool = False, mode: str | None = None) -> str:
    """Issue a fresh ticket on request; keep the database's one-time/60s policy."""
    context = _external_launch_context(app)
    if context is None:
        return ""
    target_app, uid, target = context
    search = {'보험나이·상령일': '상령일', '소득상실·비상자금': '비상자금'}.get(mode)
    if target_app == 'calculator' and search:
        parts = urlsplit(target)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['search'] = search
        target = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    cache_key = f"hw.external_launch.{target_app}"
    now = time.time()
    cached = st.session_state.get(cache_key)
    if not fresh and isinstance(cached, dict):
        if (
            cached.get("user_id") == uid
            and cached.get("target") == target
            and 0 <= now - float(cached.get("issued_at") or 0) < _EXTERNAL_LAUNCH_CACHE_SECONDS
        ):
            return str(cached.get("url") or "")

    try:
        auth = HwarangAuthService(SupabaseConfig.from_mapping(st.secrets))
        url = auth.create_launch_ticket(user_id=uid, target_app=target_app, target_url=target)
    except HwarangAuthError:
        st.session_state.pop(cache_key, None)
        return ""

    st.session_state[cache_key] = {
        "user_id": uid,
        "target": target,
        "url": url,
        "issued_at": now,
    }
    return url


def _navigate_once(navigate: Callable[..., object], page_id: str, mode: str | None = None) -> None:
    """Change route in a widget callback; Streamlit supplies the single rerun."""
    navigate(page_id, mode, state=st.session_state)


def _set_home_topic(label: str) -> None:
    st.session_state["hw_home_topic"] = label


def _launch_widget(
    app: AppSpec, label: str, *, key: str, primary: bool = False,
    help_text: str | None = None, navigate: Callable[..., object] | None = None,
    mode: str | None = None,
) -> bool:
    """Render navigation; prepare a protected-app ticket only when requested."""
    if app.external_app_key:
        from modules.shared.one_click_launch import launch_button
        launch_button(label + " ↗", key=key, primary=primary,
                      disabled=_external_launch_context(app) is None,
                      issue_url=lambda: _external_launch_url(app, fresh=True, mode=mode))
        return False
    kwargs = {}
    if navigate is not None:
        kwargs = {"on_click": _navigate_once, "args": (navigate, app.id, mode)}
    return st.button(
        label, key=key, help=help_text,
        type="primary" if primary else "secondary", use_container_width=True, **kwargs,
    )

def _search_text(app: AppSpec) -> str:
    return " ".join((app.label, app.description, *app.keywords)).lower()


def _matches(query: str, allowed: set[str]) -> list[tuple[AppSpec, str | None]]:
    found: dict[str, tuple[AppSpec, str | None]] = {}
    # Calculator purpose is carried to the external app; unrelated routes stay unchanged.
    for alias, (page_id, _mode) in SEARCH_ALIASES.items():
        if page_id in allowed and query in alias.lower():
            found[page_id] = (APP_BY_ID[page_id], _mode if page_id == 'quick_calculators' else None)
    for app in APP_BY_ID.values():
        if app.id in allowed and query in _search_text(app):
            found.setdefault(app.id, (app, None))
    return sorted(found.values(), key=lambda item: item[0].order)


@st.dialog("업데이트 안내", width="large")
def notice_dialog(notice: dict[str, object]) -> None:
    st.caption(str(notice["date"]))
    st.subheader(str(notice["title"]))
    for item in notice["items"]:
        st.write("• " + str(item))


@st.dialog("작업자료와 이용 안내")
def usage_dialog() -> None:
    st.write("사이드바에서 업무를 찾고 입력 → 결과 확인 → 저장 순서로 진행하세요.")
    for title, body in [
        ('🔎 메뉴와 원수사 찾기','홈 맨 위는 원수사 검색입니다. 업무 메뉴는 사이드바 검색에서 찾습니다. ACADEMY와 CALCULATOR는 별도 앱이며 같은 계정 권한을 사용합니다.'),
        ('📎 파일을 사용하는 업무','보장분석·컨벤션·썸머·매니저·수수료는 화면에 안내된 원본 양식을 사용하세요. 먼저 개인 정보를 제거한 사본으로 검사하고, 처리 결과의 누락·중복·미매칭 건을 확인한 뒤 내보내세요.'),
        ('🧮 계산 결과 확인','계산기의 입력 단위, 적용 기준일, 가정을 확인하세요. 조건을 바꿨다면 다시 계산해야 출력물에도 반영됩니다. 현재 탭과 새 탭 중 편한 방식으로 열 수 있습니다.'),
        ('🎓 교육과 상담 연습','아카데미에서 과정 학습·자료 다운로드·개인 진도를 확인합니다. 시뮬레이터는 그 안의 상담 훈련 기능입니다. 자유 연습의 대화·점수는 직접 선택 공유하기 전에는 관리자에게 공개되지 않습니다.'),
        ('💬 대화가 멈췄을 때','입력 문장은 실패 상태로 보존됩니다. 확정 실패라면 수정·재전송할 수 있습니다. 처리 여부 미확인은 자동 재호출하지 않습니다. 관리자는 학습 AI의 요청 확인 메뉴에서 해당 건을 확인하고 복구할 수 있습니다.'),
        ('📰 브리핑과 고객 공유','게시 날짜와 출처를 먼저 확인하세요. 고객 공유는 검수된 공개용 내용의 미리보기를 확인한 뒤 진행합니다. 생성 실패 시 운영 관리에서 원인과 미확인 비용을 확인합니다.'),
        ('🔐 계정과 권한','내 계정에서 비밀번호를 변경할 수 있습니다. 메뉴가 보이지 않으면 관리자에게 앱 접근과 기능 권한을 확인해 달라고 요청하세요.')]:
        with st.expander(title):st.write(body)


def render_sidebar(allowed_ids: list[str], navigate: Callable[..., object], logout: Callable[..., object], notice: dict[str, object]) -> None:
    allowed = set(allowed_ids)
    with st.sidebar:
        with st.container(key="hw_sidebar_header"):
            st.markdown('<div class="sig-brand"><span class="sig-mark">H</span><div><strong>화랑</strong><small>WORKSPACE</small></div></div>', unsafe_allow_html=True)
            st.button(
                "🏠 홈", key="v2_nav_home", use_container_width=True,
                type="primary" if st.session_state.get("active_app") == "home" else "secondary",
                on_click=_navigate_once, args=(navigate, "home", None),
            )
            if "briefing" in allowed:
                st.button(
                    "📰 브리핑 센터", key="hw_sidebar_briefing", use_container_width=True,
                    type="primary" if st.session_state.get("active_app") == "briefing" else "secondary",
                    on_click=_navigate_once, args=(navigate, "briefing", None),
                )
            if "analyzer" in allowed:
                with st.container(key="hw_sidebar_quick"):
                    st.button(
                        "🛡️ 보장 분석 시작", key="hw_sidebar_analyzer", use_container_width=True,
                        on_click=_navigate_once, args=(navigate, "analyzer", None),
                    )
            query = st.text_input("기능 빠른 검색", placeholder="상령일, 문자, 실손…", key="sig_nav_search").strip().lower()
        matched_ids = {app.id for app, _mode in _matches(query, allowed)} if query else allowed
        any_match = False
        for topic in _HOME_TOPICS:
            apps = [APP_BY_ID[item] for item in topic[4] if item in allowed and item in matched_ids]
            if not apps:
                continue
            any_match = True
            with st.expander({"고객 상담":"💬 고객 상담", "보험 비교 · 계산":"🧮 보험 비교 · 계산", "실적 관리":"📈 실적 관리", "자료 · 교육":"📚 자료 · 교육"}.get(topic[0], topic[0]), expanded=bool(query) or st.session_state.get("active_app") in {app.id for app in apps}):
                for app in apps:
                    _launch_widget(
                        app, app.label, key="v2_nav_" + app.id,
                        primary=st.session_state.get("active_app") == app.id, navigate=navigate,
                    )
        if query and not any_match:
            st.caption("검색 결과가 없습니다.")
        st.divider()
        if st.button("이용 안내", icon=":material/help_outline:", key="sig_usage", use_container_width=True):
            usage_dialog()
        if st.button("최근 업데이트", icon=":material/history:", key="sig_update", use_container_width=True):
            notice_dialog(notice)
        profile = st.session_state.get("login_profile") or {}
        account_name = str(profile.get("display_name") or profile.get("login_id") or "")
        account_meta = " · ".join(
            item for item in (str(profile.get("organization_name") or ""), str(profile.get("position_name") or "")) if item
        )
        st.caption("접속 계정 · " + account_name + ((" · " + account_meta) if account_meta else ""))
        st.button(
            "로그아웃", icon=":material/logout:", key="v2_logout", use_container_width=True, on_click=logout,
        )
        st.caption("Planned & Built by 박병선 팀장")






# Home tabs only change the visible tool set; registered destinations and permissions stay authoritative.
_HOME_TOPICS = (
    ("고객 상담", "CUSTOMER CONSULTING", "고객 상담을 준비하세요", "보장을 살펴보고, 고객에게 맞는 제안을 정리합니다.",
     ("analyzer", "remodeling", "consultation_helper", "comparison_builder", "insurance_claim_guide")),
    ("보험 비교 · 계산", "COMPARE & CALCULATE", "선택지를 명확하게 비교하세요", "보장과 숫자를 나란히 놓고 판단할 수 있습니다.",
     ("silson_generation_comparison", "quick_calculators", "deposit_vs_shortpay", "renewal_vs_nonrenewal", "inheritance_tax")),
    ("실적 관리", "PERFORMANCE MANAGEMENT", "업무 결과를 한눈에 확인하세요", "실적과 수수료를 정리하고 흐름을 살펴봅니다.",
     ("convention", "summer", "manager_results", "commission_calculator")),
    ("자료 · 교육", "RESOURCES & LEARNING", "업무 자료를 찾아보세요", "원수사 정보와 교육 자료를 한곳에서 확인합니다.",
     ("insurer_portal", "academy")),
)




# Home-specific symbols and tones keep each task visually recognizable.
_HOME_ICON_STYLES = {
    "analyzer": ("analysis", "blue"),
    "remodeling": ("remodeling", "teal"),
    "deposit_vs_shortpay": ("coins", "amber"),
    "renewal_vs_nonrenewal": ("remodeling", "teal"),
    "inheritance_tax": ("family", "violet"),
    "quick_calculators": ("calculator", "amber"),
    "consultation_helper": ("consultation", "violet"),
    "academy": ("education", "violet"),
    "convention": ("performance", "teal"),
    "summer": ("performance", "amber"),
    "manager_results": ("performance", "violet"),
    "commission_calculator": ("coins", "amber"),
}


_PREMIUM_EMOJI = {
    "analyzer": "🛡️", "remodeling": "🔄", "consultation_helper": "💬",
    "comparison_builder": "📊", "insurance_claim_guide": "📋", "silson_generation_comparison": "🔍",
    "quick_calculators": "🧮", "deposit_vs_shortpay": "🌱", "renewal_vs_nonrenewal": "⚖️",
    "inheritance_tax": "🏛️", "convention": "🏆", "summer": "☀️", "manager_results": "📈",
    "commission_calculator": "💼", "insurer_portal": "📂", "academy": "🎓", "briefing": "📰",
}


def render_home(allowed_ids: list[str], navigate: Callable[..., object], notice: dict[str, object]) -> None:
    from modules.shared.premium_homes import apply, identity_header, footer, emoji_markup
    apply('workspace')
    allowed = set(allowed_ids)
    profile = st.session_state.get('login_profile') or {}
    identity_header('WORKSPACE', profile)
    name = html.escape(str(profile.get('display_name') or profile.get('login_id') or '사용자'))
    if 'insurer_portal' in allowed:
        with st.container(key='hp_top_portal'):
            st.markdown('**📂 원수사 포털 빠른 검색**')
            render_home_quick_search()
    st.markdown(f'<section class="hp-welcome"><span class="hp-kicker">YOUR WORK, SIMPLIFIED</span><h1>{name}님, 오늘도 좋은 상담 되세요.</h1><p>필요한 도구를 찾고, 준비된 상담을 시작하세요.</p></section>', unsafe_allow_html=True)
    if 'analyzer' in allowed:
        with st.container(key='hp_workspace_hero'):
            copy, art = st.columns([1.15, 1], gap='large', vertical_alignment='center')
            with copy:
                st.markdown('<div class="hp-hero-copy"><span class="hp-kicker">CONSULTATION DESK</span><h2>고객의 보장을 읽고,<br>상담의 방향을 찾다.</h2><p>가입한 보장과 보험료를 정리하고<br>고객에게 필요한 질문을 준비하세요.</p></div>', unsafe_allow_html=True)
                _launch_widget(APP_BY_ID['analyzer'], '보장분석 시작 ↗', key='hw_feature_launch', primary=True, navigate=navigate)
            art.markdown('<div class="hp-art" aria-hidden="true"><div class="hp-paper"><strong>🔎 보장분석 노트</strong><span>가입 현황<i></i></span><span>보장 구성<i></i></span><span>보험료 확인<i></i></span><small>HWARANG CONSULTATION</small></div></div>', unsafe_allow_html=True)
    recent=[key for key in st.session_state.get('hw.ui.recent',[]) if key in allowed and key in APP_BY_ID][:4]
    with st.popover('⭐ 자주 쓰는 도구 설정'):
        favorites=st.multiselect('홈에 고정할 도구', [key for key in allowed_ids if key in APP_BY_ID],
            default=[key for key in st.session_state.get('hw.home.favorites',[]) if key in allowed],
            format_func=lambda key:APP_BY_ID[key].label,max_selections=4,key='hw.home.favorite_picker')
        st.session_state['hw.home.favorites']=favorites
        st.caption('이 로그인 세션에서 유지됩니다. 최근 사용은 실제로 연 도구만 표시합니다.')
    for heading, keys, prefix in [('⭐ 자주 쓰는 도구',favorites,'favorite'),('🕒 최근 사용',recent,'recent')]:
        if keys:
            st.markdown('**'+heading+'**')
            for col,key in zip(st.columns(len(keys)),keys):
                with col:_launch_widget(APP_BY_ID[key],APP_BY_ID[key].label+' →',key='hp_'+prefix+'_'+key,navigate=navigate)
    st.subheader('업무 도구')
    query = ''
    labels = ['전체'] + [t[0] for t in _HOME_TOPICS if any(i in allowed for i in t[4])]
    if st.session_state.get('hw_home_topic') not in labels:
        st.session_state['hw_home_topic'] = '전체'
    with st.container(key='hp_workspace_categories', horizontal=True):
        for label in labels:
            st.button(label, key='hw_category_'+label, type='primary' if st.session_state['hw_home_topic']==label else 'secondary', on_click=_set_home_topic, args=(label,))
    if query:
        items = _matches(query, allowed)
        st.caption(f'전체 도구 검색 결과 · {len(items)}개')
    else:
        choice = st.session_state['hw_home_topic']
        selected = next((t[4] for t in _HOME_TOPICS if t[0]==choice), tuple(i for t in _HOME_TOPICS for i in t[4]))
        items = [(APP_BY_ID[i], None) for i in selected if i in allowed]
    if not items:
        st.info('이용 가능한 도구가 없거나 검색 결과가 없습니다.')
    with st.container(key='hp_workspace_tools'):
        for start in range(0, len(items), 2):
            for col, (app, mode) in zip(st.columns(2, gap='large'), items[start:start+2]):
                with col, st.container(key='hp_tool_'+app.id):
                    icon = emoji_markup(_PREMIUM_EMOJI.get(app.id, '📁'))
                    st.markdown(f'<div class="hp-tool-copy"><span class="hp-emoji" aria-hidden="true">{icon}</span><div><h3>{html.escape(app.label)}</h3><p>{html.escape(app.description)}</p></div></div>', unsafe_allow_html=True)
                    _launch_widget(app, app.label+' 열기 →', key='hw_home_launch_'+app.id, navigate=navigate, mode=mode)
    if 'briefing' in allowed:
        st.subheader('📰 브리핑 센터')
        try:
            from modules.briefing.briefing_center import render_home_summary
            render_home_summary(navigate)
        except Exception:
            _launch_widget(APP_BY_ID['briefing'], '브리핑 센터 열기 →', key='hp_briefing_fallback', navigate=navigate)
    footer('WORKSPACE')
