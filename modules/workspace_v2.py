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
        st.markdown('<div class="sig-brand"><span class="sig-mark">H</span><div><strong>HWARANG</strong><small>WORKSPACE</small></div></div>', unsafe_allow_html=True)
        if st.button("홈", key="v2_nav_home", use_container_width=True, type="primary" if st.session_state.get("active_app") == "home" else "secondary"):
            navigate("home")
        query = st.text_input("기능 빠른 검색", placeholder="상령일, 문자, 실손…", key="sig_nav_search").strip().lower()
        matched_ids = {app.id for app, _mode in _matches(query, allowed)} if query else allowed
        any_match = False
        for group in GROUPS:
            apps = [app for app in _group_apps(group.id, allowed) if app.id in matched_ids]
            if not apps:
                continue
            any_match = True
            with st.expander(group.label, expanded=bool(query) or st.session_state.get("active_app") in {app.id for app in apps}):
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


def render_home(allowed_ids: list[str], navigate: Callable[..., object], notice: dict[str, object]) -> None:
    allowed = set(allowed_ids)
    st.markdown(
        f'<div class="sig-intro"><div class="sig-eyebrow">HWARANG WORKSPACE · {date.today():%Y.%m.%d}</div>'
        '<h1>오늘의 상담을 더 명료하게.</h1><p>현재 접속에서 필요한 도구를 찾고 업무를 이어가세요.</p></div>',
        unsafe_allow_html=True,
    )
    query = st.text_input("화랑 도구 검색", key="v2_global_search", placeholder="보험나이, 상담 문자, 비교표, 청구서류…").strip().lower()
    if query:
        matches = _matches(query, allowed)
        st.subheader(f"검색 결과 · {len(matches)}개")
        if not matches:
            st.info("관련 도구가 없습니다. 더 짧은 단어로 검색하세요.")
        _grid(matches, navigate, "search")
    if "insurer_portal" in allowed:
        with st.container(border=True):
            st.subheader("원수사 바로 검색")
            render_home_quick_search()
            st.caption("보험사명과 별칭으로 전산·대표 연락처를 찾습니다. 화랑 도구 검색과 별도입니다.")
    if not query:
        st.subheader("빠른 시작")
        quick_ids = ("consultation_helper", "quick_calculators", "analyzer", "comparison_builder")
        _grid([(APP_BY_ID[app_id], None) for app_id in quick_ids if app_id in allowed], navigate, "quick")
        recent = [app_id for app_id in st.session_state.get("hw.ui.recent", st.session_state.get("sig_recent", [])) if app_id in allowed][:4]
        if recent:
            st.subheader("최근 사용한 도구")
            for column, app_id in zip(st.columns(len(recent)), recent):
                if column.button(APP_BY_ID[app_id].label, key="sig_recent_" + app_id, use_container_width=True):
                    navigate(app_id)
        st.subheader("센터별 도구")
        for group in GROUPS:
            apps = _group_apps(group.id, allowed)
            if not apps:
                continue
            with st.expander(f"{group.label} · {len(apps)}", expanded=False):
                st.caption(group.description)
                _grid([(app, None) for app in apps], navigate, "all")
    st.divider()
    st.caption(f"{notice['date']} · {notice['title']} · 변경 내용을 확인하세요.")
    update_col, privacy_col = st.columns(2)
    if update_col.button("변경 내용 보기", key="sig_home_notice", use_container_width=True):
        notice_dialog(notice)
    if privacy_col.button("자료 이용 안내", key="sig_home_privacy", use_container_width=True):
        usage_dialog()
    st.markdown('<div class="sig-footer">HWARANG WORKSPACE · Test Server<br>Planned &amp; Built by 박병선 팀장</div>', unsafe_allow_html=True)
