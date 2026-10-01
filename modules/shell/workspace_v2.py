"""Single home and sidebar implementation for the Stage 2 framework."""
from __future__ import annotations

import html
from typing import Callable

import streamlit as st

from modules.shell.app_registry import APP_BY_ID, SEARCH_ALIASES, AppSpec
from modules.resources.insurer_portal import render_home_quick_search
from modules.shared.external_apps import external_app_url

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






def _launch_widget(app: AppSpec, label: str, *, key: str, primary: bool = False, help_text: str | None = None) -> bool:
    """Render an internal navigation button or a separate-app new-tab link."""
    if app.external_app_key:
        url = external_app_url(app.external_app_key)
        st.link_button(
            label + " ↗",
            url or "https://example.invalid",
            key=key,
            help=help_text,
            type="primary" if primary else "secondary",
            disabled=not bool(url),
            use_container_width=True,
        )
        return False
    return st.button(
        label,
        key=key,
        help=help_text,
        type="primary" if primary else "secondary",
        use_container_width=True,
    )

def _search_text(app: AppSpec) -> str:
    return " ".join((app.label, app.description, *app.keywords)).lower()


def _matches(query: str, allowed: set[str]) -> list[tuple[AppSpec, str | None]]:
    found: dict[str, tuple[AppSpec, str | None]] = {}
    # Alias matches currently route to the page. Page-specific mode consumption
    # remains a later feature-stage integration.
    for alias, (page_id, _mode) in SEARCH_ALIASES.items():
        if page_id in allowed and query in alias.lower():
            found[page_id] = (APP_BY_ID[page_id], None)
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
            if st.button("홈", icon=":material/home:", key="v2_nav_home", use_container_width=True, type="primary" if st.session_state.get("active_app") == "home" else "secondary"):
                navigate("home")
            if "analyzer" in allowed:
                with st.container(key="hw_sidebar_quick"):
                    if st.button("보장 분석 시작", icon=":material/shield:", key="hw_sidebar_analyzer", use_container_width=True):
                        navigate("analyzer")
            query = "" if st.session_state.get("active_app") == "home" else st.text_input("기능 빠른 검색", placeholder="상령일, 문자, 실손…", key="sig_nav_search").strip().lower()
        matched_ids = {app.id for app, _mode in _matches(query, allowed)} if query else allowed
        any_match = False
        for topic in _HOME_TOPICS:
            apps = [APP_BY_ID[item] for item in topic[4] if item in allowed and item in matched_ids]
            if not apps:
                continue
            any_match = True
            with st.expander(topic[0], expanded=bool(query) or st.session_state.get("active_app") in {app.id for app in apps}):
                for app in apps:
                    launched = _launch_widget(
                        app, app.label, key="v2_nav_" + app.id,
                        primary=st.session_state.get("active_app") == app.id,
                    )
                    if launched:
                        navigate(app.id)
        if query and not any_match:
            st.caption("검색 결과가 없습니다.")
        st.divider()
        if st.button("이용 안내", icon=":material/help_outline:", key="sig_usage", use_container_width=True):
            usage_dialog()
        if st.button("최근 업데이트", icon=":material/history:", key="sig_update", use_container_width=True):
            notice_dialog(notice)
        st.caption("접속 계정 · " + str(st.session_state.get("login_user", "")))
        if st.button("로그아웃", icon=":material/logout:", key="v2_logout", use_container_width=True):
            logout()
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
     ("insurer_portal", "education_center")),
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
    "education_center": ("education", "violet"),
    "convention": ("performance", "teal"),
    "summer": ("performance", "amber"),
    "manager_results": ("performance", "violet"),
    "commission_calculator": ("coins", "amber"),
}


def render_home(allowed_ids: list[str], navigate: Callable[..., object], notice: dict[str, object]) -> None:
    allowed = set(allowed_ids)
    with st.container(key="hw_dashboard"):
        st.markdown('<div class="hw-dashboard-marker"></div>', unsafe_allow_html=True)
        with st.container(key="hw_home_welcome"):
            welcome, portal = st.columns([1.1, 1], gap="large", vertical_alignment="center")
            with welcome:
                st.markdown('<div class="hw-welcome-copy"><span>HWARANG WORKSPACE</span><h1>오늘의 업무를 시작해 볼까요?</h1><p>상담부터 관리까지, 필요한 도구를 한곳에서.</p></div>', unsafe_allow_html=True)
            if "insurer_portal" in allowed:
                with portal:
                    st.markdown('<div class="hw-dash-search-label">원수사 포털 검색</div>', unsafe_allow_html=True)
                    render_home_quick_search()
        if "analyzer" in allowed:
            with st.container(key="hw_mobile_quick"):
                if st.button("보장 분석 시작", icon=":material/shield:", key="hw_feature_launch", use_container_width=True):
                    navigate("analyzer")
        work_title, work_search = st.columns([1, 1.3], gap="large", vertical_alignment="center")
        with work_title:
            st.subheader("어떤 도구가 필요하세요?")
        with work_search:
            query = st.text_input("기능 찾기", key="v2_global_search", placeholder="보장, 연금, 실적 등 업무 검색", label_visibility="collapsed").strip().lower()
        labels = [topic[0] for topic in _HOME_TOPICS if any(item in allowed for item in topic[4])]
        if not labels:
            st.info("이용할 수 있는 도구가 없습니다.")
            return
        if st.session_state.get("hw_home_topic") not in labels:
            st.session_state["hw_home_topic"] = labels[0]
        with st.container(key="hw_category_navigation"):
            for column, label in zip(st.columns(len(labels), gap="small"), labels):
                with column:
                    if st.button(label, key="hw_category_" + label,
                                 type="primary" if st.session_state["hw_home_topic"] == label else "secondary",
                                 use_container_width=True):
                        st.session_state["hw_home_topic"] = label
                        st.rerun()
        choice = st.session_state["hw_home_topic"]
        selected = next(topic for topic in _HOME_TOPICS if topic[0] == choice)
        if query:
            items = _matches(query, allowed)
            st.caption(f"전체 도구 검색 결과 · {len(items)}개")
        else:
            items = [(APP_BY_ID[item], None) for item in selected[4] if item in allowed]
            st.caption(selected[2])
        if not items:
            st.info("검색 결과가 없습니다. 다른 업무명으로 검색해 보세요.")
        with st.container(key="hw_tool_grid"):
            for start in range(0, len(items), 3):
                for column, (app, mode) in zip(st.columns(3, gap="medium"), items[start:start + 3]):
                    with column, st.container(key=f"hw_dash_tool_{app.id}"):
                        icon_key, tone = _HOME_ICON_STYLES.get(app.id, (app.icon_key, "blue"))
                        icon = _ICONS.get(icon_key, _ICONS["materials"])
                        st.markdown(f'<div class="hw-tool-heading"><span class="hw-tool-symbol hw-icon-{tone}" aria-hidden="true">{icon}</span><h3>{html.escape(app.label)}</h3></div><p class="hw-dash-tool-desc">{html.escape(app.description)}</p>', unsafe_allow_html=True)
                        launched = _launch_widget(
                            app, app.label + " 열기 →", key="hw_home_launch_" + app.id,
                            help_text=None if app.external_app_key else f"{app.label} 열기",
                        )
                        if launched:
                            navigate(app.id, mode)
        st.markdown('<div class="hw-dash-footer">Planned &amp; Built by 박병선 팀장 · 보험 업무의 복잡함, 더 간단하게.</div>', unsafe_allow_html=True)
