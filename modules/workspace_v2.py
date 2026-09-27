"""Single home and sidebar implementation for the Stage 2 framework."""
from __future__ import annotations

import html
from datetime import date
from typing import Callable

import streamlit as st

from .app_registry import APP_BY_ID, GROUPS, SEARCH_ALIASES, AppSpec
from .insurer_portal import render_home_quick_search
from .privacy_guard import environment_notice

_ICONS = {
    "consultation": '<svg viewBox="0 0 24 24"><path d="M5 4h14v12H9l-4 4z"/><path d="M8 8h8M8 12h5"/></svg>',
    "calculator": '<svg viewBox="0 0 24 24"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h2M12 11h2M16 11h1M8 15h2M12 15h2M16 15h1"/></svg>',
    "analysis": '<svg viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 11h6M9 15h6"/></svg>',
    "materials": '<svg viewBox="0 0 24 24"><path d="M7 3h10v18H7z"/><path d="M10 8h4M9 12h6M9 16h6"/></svg>',
    "education": '<svg viewBox="0 0 24 24"><path d="M3 6l9-3 9 3-9 3z"/><path d="M6 8v6c3 2 9 2 12 0V8M21 6v8"/></svg>',
    "official": '<svg viewBox="0 0 24 24"><path d="M5 3h14v18H5z"/><path d="M8 7h8M8 11h8M8 15h5"/></svg>',
    "performance": '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V6M16 20V3M22 20H2"/></svg>',
    "compare": '<svg viewBox="0 0 24 24"><path d="M7 5h13M17 2l3 3-3 3M17 19H4M7 16l-3 3 3 3"/></svg>',
    "remodeling": '<svg viewBox="0 0 24 24"><path d="M20 7h-5V2M20 7a8 8 0 10 0 10"/></svg>',
    "tax": '<svg viewBox="0 0 24 24"><path d="M6 3h12v18H6zM9 8h6M9 12h2M13 12h2M9 16h6"/></svg>',
    "medical": '<svg viewBox="0 0 24 24"><path d="M12 3l8 3v5c0 5-3 8-8 10-5-2-8-5-8-10V6zM12 8v6M9 11h6"/></svg>',
}


def _group_apps(group_id: str, allowed: set[str]) -> list[AppSpec]:
    return sorted((app for app in APP_BY_ID.values() if app.group_id == group_id and app.id in allowed), key=lambda app: app.order)


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
        st.markdown('<div class="sig-brand"><span class="sig-mark">H</span><div><strong>화랑</strong><small>WORKSPACE</small></div></div>', unsafe_allow_html=True)
        if st.button("⌂  홈", key="v2_nav_home", use_container_width=True, type="primary" if st.session_state.get("active_app") == "home" else "secondary"):
            navigate("home")
        if "analyzer" in allowed:
            with st.container(key="hw_sidebar_quick"):
                if st.button("🛡️ 보장 분석 시작 ↗", key="hw_sidebar_analyzer", use_container_width=True):
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
                    if st.button(app.label, key="v2_nav_" + app.id, type="primary" if st.session_state.get("active_app") == app.id else "secondary", use_container_width=True):
                        navigate(app.id)
        if query and not any_match:
            st.caption("검색 결과가 없습니다.")
        st.divider()
        if st.button("이용 안내", key="sig_usage", use_container_width=True):
            usage_dialog()
        if st.button("최근 업데이트", key="sig_update", use_container_width=True):
            notice_dialog(notice)
        st.caption("접속 계정 · " + str(st.session_state.get("login_user", "")))
        if st.button("로그아웃", key="v2_logout", use_container_width=True):
            logout()
        st.caption("Planned & Built by 박병선 팀장")


def _tool_card(app: AppSpec, navigate: Callable[..., object], prefix: str, mode: str | None = None) -> None:
    with st.container(border=True, key=f"sig_card_{prefix}_{app.id}"):
        st.markdown(
            f'<div class="sig-icon" aria-hidden="true">{_ICONS.get(app.icon_key, _ICONS["materials"])}</div>'
            f'<div class="sig-card-title">{html.escape(app.label)}</div>'
            f'<div class="sig-card-desc">{html.escape(app.description)}</div>',
            unsafe_allow_html=True,
        )
        if st.button("열기 →", key=f"v2_launch_{prefix}_{app.id}", use_container_width=True):
            navigate(app.id, mode)


def _grid(items: list[tuple[AppSpec, str | None]], navigate: Callable[..., object], prefix: str) -> None:
    for start in range(0, len(items), 3):
        for column, (app, mode) in zip(st.columns(3, gap="medium"), items[start:start + 3]):
            with column:
                _tool_card(app, navigate, prefix, mode)


# Home tabs only change the visible tool set; registered destinations and permissions stay authoritative.
_HOME_TOPICS = (
    ("고객 상담", "CUSTOMER CONSULTING", "고객 상담을 준비하세요", "보장을 살펴보고, 고객에게 맞는 제안을 정리합니다.",
     ("analyzer", "remodeling", "consultation_helper", "comparison_builder", "customer_materials", "insurance_claim_guide")),
    ("보험 비교 · 계산", "COMPARE & CALCULATE", "선택지를 명확하게 비교하세요", "보장과 숫자를 나란히 놓고 판단할 수 있습니다.",
     ("silson_generation_comparison", "quick_calculators", "deposit_vs_shortpay", "renewal_vs_nonrenewal", "inheritance_tax")),
    ("실적 관리", "PERFORMANCE MANAGEMENT", "업무 결과를 한눈에 확인하세요", "실적과 수수료를 정리하고 흐름을 살펴봅니다.",
     ("convention", "summer", "manager_results", "commission_calculator")),
    ("자료 · 교육", "RESOURCES & LEARNING", "업무 자료를 찾아보세요", "원수사 정보와 교육 자료를 한곳에서 확인합니다.",
     ("insurer_portal", "education_center")),
)


_HOME_EMOJI = {"analysis": "🛡️", "consultation": "💬", "calculator": "🧮", "compare": "⚖️", "remodeling": "🔄", "materials": "📋", "education": "📚", "official": "🏢", "performance": "📊", "medical": "🔎", "tax": "🧾", "claim": "📑"}


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
                if st.button("🛡️ 보장 분석 시작 →", key="hw_feature_launch", use_container_width=True):
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
                        emoji = _HOME_EMOJI.get(app.icon_key, "📁")
                        st.markdown(f'<div class="hw-tool-heading"><span class="hw-tool-symbol">{emoji}</span><h3>{html.escape(app.label)}</h3></div><p class="hw-dash-tool-desc">{html.escape(app.description)}</p>', unsafe_allow_html=True)
                        if st.button("시작하기 →", key="hw_home_launch_" + app.id, use_container_width=True):
                            navigate(app.id, mode)
        st.markdown('<div class="hw-dash-footer">Planned &amp; Built by 박병선 팀장 · 보험 업무의 복잡함, 더 간단하게.</div>', unsafe_allow_html=True)
