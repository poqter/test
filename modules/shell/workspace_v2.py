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
    st.write("도구를 선택하고 입력한 뒤 결과를 확인하세요. 필요한 자료는 내려받을 수 있습니다.")


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
            query = "" if st.session_state.get("active_app") == "home" else st.text_input("기능 빠른 검색", placeholder="상령일, 문자, 실손…", key="sig_nav_search").strip().lower()
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
    st.markdown(f'<section class="hp-welcome"><span class="hp-kicker">YOUR WORK, SIMPLIFIED</span><h1>{name}님, 오늘도 좋은 상담 되세요.</h1><p>필요한 도구를 찾고, 준비된 상담을 시작하세요.</p></section>', unsafe_allow_html=True)
    if 'analyzer' in allowed:
        with st.container(key='hp_workspace_hero'):
            copy, art = st.columns([1.15, 1], gap='large', vertical_alignment='center')
            with copy:
                st.markdown('<div class="hp-hero-copy"><span class="hp-kicker">CONSULTATION DESK</span><h2>고객의 보장을 읽고,<br>상담의 방향을 찾다.</h2><p>가입한 보장과 보험료를 정리하고<br>고객에게 필요한 질문을 준비하세요.</p></div>', unsafe_allow_html=True)
                _launch_widget(APP_BY_ID['analyzer'], '보장분석 시작 ↗', key='hw_feature_launch', primary=True, navigate=navigate)
            art.markdown('<div class="hp-art" aria-hidden="true"><div class="hp-paper"><strong>🔎 보장분석 노트</strong><span>가입 현황<i></i></span><span>보장 구성<i></i></span><span>보험료 확인<i></i></span><small>HWARANG CONSULTATION</small></div></div>', unsafe_allow_html=True)
    title, search = st.columns([1, 1.4], vertical_alignment='center')
    title.subheader('업무 도구')
    with search, st.container(key='hp_workspace_search'):
        query = st.text_input('업무 도구 검색', key='v2_global_search', placeholder='보장, 실손, 자료, 실적…', label_visibility='collapsed').strip().lower()
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
    if 'insurer_portal' in allowed:
        with st.expander('📂 원수사 포털 빠른 검색'):
            render_home_quick_search()
    footer('WORKSPACE')
