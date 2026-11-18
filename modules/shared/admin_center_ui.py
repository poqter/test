"""Super-admin account, authorization and operational views."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import html
import time
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st
from modules.shared.refresh import refresh_current

from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService
from importlib.util import find_spec
from modules.shared.external_apps import academy_url, calculator_url


_KST = ZoneInfo("Asia/Seoul")
_ROLE_LABELS = {
    "user": "일반 사용자",
    "admin": "관리자",
    "super_admin": "최고관리자",
}
_APP_LABELS = {
    "workspace": "WORKSPACE",
    "calculator": "CALCULATOR",
    "academy": "ACADEMY",
}
_UNIT_LABELS = {
    "root": "전체",
    "head_unit": "본부/직할",
    "branch": "지점/직할",
    "team": "팀",
}
_PAGE_LABELS = {
    "dashboard": "대시보드",
    "operations": "운영 점검",
    "accounts": "계정 · 권한",
    "assets": "상담 자산",
    "simulator_dashboard": "상담 운영 현황",
    "academy": "상담 이력 · 평가",
    "ai": "AI 사용량 · 비용",
    "settings": "시스템 설정",
}
_PAGE_SUBTITLES = {
    "dashboard": "플랫폼 운영 상태와 지금 확인해야 할 항목을 한눈에 봅니다.",
    "operations": "문제와 근거를 확인하고 점검 기록·요청문을 정리합니다.",
    "accounts": "사용자 계정, 앱 접근권한, 세부 기능 권한을 관리합니다.",
    "assets": "상담 자산의 배정과 조정 이력을 확인합니다.",
    "simulator_dashboard": "상담 세션과 이용량을 확인합니다.",
    "academy": "상담 훈련 Session과 평가 결과를 운영 관점에서 확인합니다.",
    "ai": "AI 사용량, 비용, 차단·실패 내역을 운영합니다.",
    "settings": "AI 서비스, 크레딧 정책, 모델·Guardrail과 위험 작업을 관리합니다.",
}

_EVENT_LABELS = {
    "LOGIN_SUCCESS": "WORKSPACE 로그인",
    "LOGOUT": "로그아웃",
    "APP_OPENED": "기능 열기",
    "FEATURE_OPENED": "기능 열기",
    "FEATURE_EXECUTED": "기능 실행",
    "ADMIN_CENTER_OPENED": "관리자 센터 열기",
    "PDF_GENERATED": "PDF 생성",
    "EXCEL_GENERATED": "Excel 생성",
    "FILE_DOWNLOADED": "파일 다운로드",
    "CASE_CREATED": "ACADEMY 고객 Case 생성",
    "SIMULATION_STARTED": "상담 훈련 시작",
    "SIMULATION_COMPLETED": "상담 훈련 완료",
    "ASSESSMENT_GENERATED": "AI 평가 생성",
    "AI_REQUEST_BLOCKED": "AI 요청 차단",
    "ERROR_OCCURRED": "오류 발생",
}
_ADMIN_ACTION_LABELS = {
    "account_permissions_updated": "계정·권한 변경",
    "ai_runtime_updated": "AI 운영 설정 변경",
    "ai_model_policy_updated": "AI 모델 정책 변경",
    "credit_policy_updated": "크레딧 정책 변경",
    "purchased_credit_grant": "구매/추가 크레딧 지급",
    "purchased_credit_revoke": "구매/추가 크레딧 회수",
    "purchased_credit_reset": "구매/추가 크레딧 재설정",
    "bulk_purchased_credit_grant": "구매/추가 크레딧 일괄 지급",
    "bulk_purchased_credit_adjustment": "훈련 크레딧 일괄 조정",
    "bulk_voice_adjustment": "Voice 일괄 조정",
    "voice_minutes_grant": "Voice 이용량 지급",
    "voice_minutes_revoke": "Voice 이용량 회수",
    "voice_minutes_reset": "Voice 이용량 재설정",
}


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------
def _require_actor(auth: HwarangAuthService) -> tuple[str, dict[str, Any]]:
    viewer = st.session_state.get("login_profile") or {}
    actor_id = str(viewer.get("id") or "")
    if viewer.get("role") != "super_admin" or not actor_id:
        raise HwarangAuthError("관리자 센터는 최고관리자만 이용할 수 있습니다.")
    auth._require_super_admin(actor_id)
    return actor_id, viewer


def _safe_rows(
    auth: HwarangAuthService,
    path: str,
    *,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = auth._request("GET", path, admin=True, params=params)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise HwarangAuthError("조회 결과를 확인하지 못했습니다. 다시 조회해 주세요.")
    return rows


_ADMIN_READ_CACHE_KEY = "hw_admin_read_cache_v1"


def _cached_admin_read(cache_key: str, ttl_seconds: int, loader):
    """Cache short-lived admin read results within the current Streamlit session."""
    actor = str((st.session_state.get("login_profile") or {}).get("id") or "")
    if st.session_state.get("hw_admin_read_cache_owner") != actor:
        st.session_state.pop(_ADMIN_READ_CACHE_KEY, None)
        st.session_state["hw_admin_read_cache_owner"] = actor
    cache = st.session_state.get(_ADMIN_READ_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[_ADMIN_READ_CACHE_KEY] = cache

    now = time.time()
    entry = cache.get(str(cache_key))
    if isinstance(entry, dict):
        age = now - float(entry.get("at") or 0)
        if age >= 0 and age < max(0, int(ttl_seconds)):
            return entry.get("data")

    data = loader()
    if data is not None:
        cache[str(cache_key)] = {"at": now, "data": data}
        while len(cache) > 32:
            cache.pop(next(iter(cache)))
    return data


def _clear_admin_read_cache(prefix: str | None = None) -> None:
    """Invalidate admin read cache after a state-changing administrator action."""
    if prefix is None:
        st.session_state.pop(_ADMIN_READ_CACHE_KEY, None)
        return
    cache = st.session_state.get(_ADMIN_READ_CACHE_KEY)
    if not isinstance(cache, dict):
        return
    prefix = str(prefix)
    for key in list(cache):
        if str(key).startswith(prefix):
            cache.pop(key, None)


def _fmt_dt(value: Any) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)[:16].replace("T", " ")


def _fmt_relative(value: Any) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        seconds = max(0, int(diff.total_seconds()))
        if seconds < 60:
            return "방금 전"
        if seconds < 3600:
            return f"{seconds // 60}분 전"
        if seconds < 86400:
            return f"{seconds // 3600}시간 전"
        if seconds < 86400 * 7:
            return f"{seconds // 86400}일 전"
        return _fmt_dt(value)
    except Exception:
        return _fmt_dt(value)


def _active_recent(value: Any, minutes: int = 10) -> bool:
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (
            datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        ).total_seconds() <= minutes * 60
    except Exception:
        return False

def _logged_in_today(value: Any) -> bool:
    if not value: return False
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_KST).date()==datetime.now(_KST).date()
    except Exception: return False


def _day_start_utc_iso() -> str:
    now = datetime.now(_KST)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()


def _month_start_utc_iso() -> str:
    now = datetime.now(_KST)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()


def _last_24h_utc_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .hw-admin-kicker{font-size:11px;font-weight:850;letter-spacing:.12em;color:#7890a8;margin-bottom:7px}
        .hw-admin-title{font-size:30px;font-weight:900;letter-spacing:-.045em;color:#15334f;line-height:1.15}
        .hw-admin-subtitle{margin-top:7px;color:#718397;font-size:13px;line-height:1.65}
        .hw-admin-time{font-size:11px;color:#8a9aab;text-align:right;padding-top:7px}
        .hw-admin-card{border:1px solid #e2e9f0;border-radius:15px;background:#fff;padding:16px 17px;box-shadow:0 4px 18px rgba(29,61,91,.035)}
        .hw-admin-card-title{font-size:12px;font-weight:850;color:#60768a;margin-bottom:8px}
        .hw-admin-card-value{font-size:25px;font-weight:900;letter-spacing:-.035em;color:#183750}
        .hw-admin-card-note{margin-top:4px;font-size:11px;color:#8797a7}
        .hw-status-row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:8px 0;border-bottom:1px solid #eef3f7;font-size:12px}
        .hw-status-row:last-child{border-bottom:0}
        .hw-status-label{font-weight:750;color:#415c74}
        .hw-chip{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:850;white-space:nowrap;background:#edf3f8;color:#506b82}
        .hw-chip.good{background:#e9f6ef;color:#28724b}.hw-chip.warn{background:#fff4dc;color:#9a671f}.hw-chip.bad{background:#faeaea;color:#9d4141}.hw-chip.off{background:#f0f2f5;color:#6b7580}
        .hw-alert{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:12px 13px;border:1px solid #e4ebf2;border-radius:13px;background:#fff;margin-bottom:8px}
        .hw-alert strong{font-size:12px;color:#1d3d59}.hw-alert small{display:block;margin-top:3px;color:#8292a2;font-size:11px}
        .hw-alert-priority{font-size:9px;font-weight:900;letter-spacing:.05em;padding:4px 7px;border-radius:999px}.hw-alert-priority.high{background:#faeaea;color:#9f4040}.hw-alert-priority.medium{background:#fff3da;color:#97631b}.hw-alert-priority.low{background:#edf3f8;color:#5f7182}
        .hw-profile-card{display:flex;align-items:center;gap:15px;border:1px solid #dfe7ef;border-radius:16px;background:#fff;padding:17px 18px;margin:4px 0 13px}
        .hw-profile-avatar{width:48px;height:48px;border-radius:14px;background:#153c61;color:#fff;display:grid;place-items:center;font-size:16px;font-weight:900;flex:0 0 auto}
        .hw-profile-name{font-size:21px;font-weight:900;color:#173750;letter-spacing:-.03em}.hw-profile-meta{font-size:12px;color:#7d8fa0;margin-top:4px}
        .hw-section-head{margin:17px 0 8px;font-size:14px;font-weight:900;color:#1b3c58}
        .hw-policy-note{padding:11px 13px;border-radius:12px;background:#f4f7fa;color:#63788b;font-size:11px;line-height:1.7}
        .hw-danger{border:1px solid #efcaca;border-radius:15px;background:#fff8f8;padding:15px 16px;margin-top:10px}.hw-danger strong{color:#9d4141}.hw-danger p{color:#7b6262;font-size:12px;margin:5px 0 0}
        [data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
        [data-testid="stMetric"]{border:1px solid #e3eaf1;border-radius:13px;background:white;padding:10px 12px}
        div[data-testid="stForm"]{border:1px solid #e2e9f0;border-radius:15px;background:#fff;padding:15px 16px}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(title: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="hw-admin-card">
          <div class="hw-admin-card-title">{html.escape(title)}</div>
          <div class="hw-admin-card-value">{html.escape(value)}</div>
          <div class="hw-admin-card-note">{html.escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _chip(label: str, kind: str = "off") -> str:
    return f'<span class="hw-chip {html.escape(kind)}">{html.escape(label)}</span>'


def _top_header(page: str) -> None:
    c1, c2 = st.columns([1, .35], vertical_alignment="top")
    with c1:
        st.markdown(
            f"""
            <div class="hw-admin-kicker">HWARANG PLATFORM MANAGEMENT</div>
            <div class="hw-admin-title">{html.escape(_PAGE_LABELS[page])}</div>
            <div class="hw-admin-subtitle">{html.escape(_PAGE_SUBTITLES[page])}</div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="hw-admin-time">{datetime.now(_KST).strftime("%Y.%m.%d %H:%M")} · KST</div>',
            unsafe_allow_html=True,
        )
    st.write("")


def _cached_reference_data(auth: HwarangAuthService, actor_id: str) -> dict[str, list[dict[str, Any]]]:
    key = "hw_admin_reference_cache"
    cached = st.session_state.get(key)
    now = time.time()
    if isinstance(cached, dict) and cached.get('actor') == actor_id and 0 <= now - float(cached.get("at") or 0) < 60:
        return dict(cached.get("data") or {})
    data = auth.admin_reference_data(actor_id)
    st.session_state[key] = {"at": now, "data": data, "actor": actor_id}
    return data


_SIMULATOR_PERMISSIONS = {"academy.simulator", "academy.formal_ai_assessment", "academy.voice_simulator"}


def _simulator_available():
    return all(find_spec(name) is not None for name in (
        "hwarang_academy.studio", "modules.shared.admin_assets", "modules.shared.ai_guardrails",
        "modules.shared.simulator_admin_ui",
    ))


def _fetch_users(auth):
    return _cached_admin_read("reference:profiles", 15, lambda: _safe_rows(
        auth, "/rest/v1/profiles_admin_view",
        params={"select": "*", "order": "display_name.asc.nullslast,login_id.asc"},
    ))


def _render_dashboard(auth, actor_id):
    st.button("새로고침", key="hw_dashboard_refresh", on_click=_clear_admin_read_cache)
    users = _fetch_users(auth)
    cols = st.columns(3)
    cols[0].metric("전체 사용자", len(users))
    cols[1].metric("오늘 로그인", sum(_logged_in_today(user.get("last_login_at")) for user in users))
    cols[2].metric("비활성 계정", sum(not user.get("is_active") for user in users))
    rows = _cached_admin_read("dashboard:recent_logins", 15, lambda: _safe_rows(
        auth, "/rest/v1/hwarang_activity_log", params={
            "select": "user_id,app_code,created_at", "event_code": "eq.LOGIN_SUCCESS",
            "order": "created_at.desc", "limit": "12",
        },
    ))
    st.subheader("최근 로그인")
    names = {str(user["user_id"]): user.get("display_name") or user.get("login_id") for user in users}
    if rows:
        st.dataframe([{"시간": _fmt_relative(row.get("created_at")), "사용자": names.get(str(row.get("user_id")), "-"),
                       "로그인 앱": _APP_LABELS.get(row.get("app_code"), "-")} for row in rows],
                     hide_index=True, use_container_width=True)
    else:
        st.caption("아직 로그인 기록이 없습니다.")
    st.button("계정 · 권한 열기", on_click=_page_change, args=("accounts",))
    st.button("운영 점검 열기", on_click=_page_change, args=("operations",))
    st.subheader("앱 연결 구성")
    for label, url in (("ACADEMY", academy_url()), ("CALCULATOR", calculator_url())):
        st.caption(f"{label} · {'연결 구성' if url else '주소 미설정'}")


def _render_accounts(auth, actor_id):
    users = _fetch_users(auth)
    selected_id = st.session_state.get("hw_admin_selected_user_id")
    selected = next((row for row in users if str(row["user_id"]) == selected_id), None)
    if selected:
        _render_user_header(selected)
        _user_permissions(auth, actor_id, selected_id)
        return
    filtered = _account_filters(users)
    if not filtered:
        st.info("조건에 맞는 계정이 없습니다.")
        return
    event = st.dataframe([{
        "사용자": row.get("display_name"), "로그인 ID": row.get("login_id"), "소속": row.get("organization_name"),
        "직책": row.get("position_name"), "시스템 권한": row.get("system_role_name"),
        "계정": "활성" if row.get("is_active") else "비활성", "최근 접속": _fmt_relative(row.get("last_login_at")),
        "ACADEMY": "사용 가능" if row.get("academy_access") else "제한",
    } for row in filtered], hide_index=True, use_container_width=True, on_select="rerun",
        selection_mode="single-row", key="hw_admin_profile_table")
    indices = event.selection.rows
    if indices and 0 <= indices[0] < len(filtered) and st.button("선택 계정 상세", type="primary"):
        st.session_state["hw_admin_selected_user_id"] = str(filtered[indices[0]]["user_id"])
        refresh_current()


def _page_change(page: str) -> None:
    st.session_state["hw_admin_center_page"] = page
    if page != "accounts": st.session_state.pop("hw_admin_selected_user_id", None)
    if page != "assets": st.session_state.pop("hw_admin_asset_user_id", None)

def _exit_admin_center() -> None:
    st.session_state["hw_admin_center_open"] = False; st.session_state["hw_admin_center_page"] = "dashboard"

def _back_to_accounts() -> None:
    st.session_state.pop("hw_admin_selected_user_id", None)


# ---------------------------------------------------------------------------
# Dedicated administrator sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    current = st.session_state.setdefault("hw_admin_center_page", "dashboard")
    with st.sidebar:
        st.markdown("### 관리자 센터")
        st.caption("HWARANG PLATFORM")
        st.write("")

        groups = [
            ("운영", [("dashboard", "대시보드"), ("operations", "운영 점검"), ("accounts", "계정 · 권한")]),
        ]
        if _simulator_available():
            groups.append(("삭제 예정 · 상담 시뮬레이터", [
                ("simulator_dashboard", "상담 운영 현황"), ("assets", "Credit · Voice"),
                ("academy", "상담 이력 · 평가"), ("ai", "사용량 · 비용"), ("settings", "학습 · 브리핑 AI 설정"),
            ]))
        for group, items in groups:
            st.caption(group)
            for code, label in items:
                st.button(label,key=f"hw_admin_nav_{code}",type="primary" if current==code else "secondary",use_container_width=True,on_click=_page_change,args=(code,))
            st.write("")

        st.divider()
        st.button("← WORKSPACE로 돌아가기",key="hw_admin_exit",use_container_width=True,on_click=_exit_admin_center)


# ---------------------------------------------------------------------------
# Accounts / User detail
# ---------------------------------------------------------------------------
def _account_filters(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    st.markdown('<div class="hw-section-head">사용자 계정</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1.7, 1, 1, 1])
    search = c1.text_input("검색", placeholder="이름 · ID · 소속 검색", label_visibility="collapsed", key="hw_admin_account_search")
    orgs = sorted({str(u.get("organization_name") or "") for u in users if u.get("organization_name")})
    positions = sorted({str(u.get("position_name") or "") for u in users if u.get("position_name")})
    org = c2.selectbox("소속", ["소속 전체", *orgs], label_visibility="collapsed", key="hw_admin_org_filter")
    position = c3.selectbox("직책", ["직책 전체", *positions], label_visibility="collapsed", key="hw_admin_position_filter")
    active = c4.selectbox("상태", ["계정 전체", "활성", "비활성"], label_visibility="collapsed", key="hw_admin_active_filter")

    q = search.strip().casefold()
    result = []
    for u in users:
        hay = " ".join(str(u.get(k) or "") for k in (
            "display_name", "login_id", "organization_name",
            "parent_organization_name", "position_name"
        )).casefold()
        if q and q not in hay:
            continue
        if org != "소속 전체" and u.get("organization_name") != org:
            continue
        if position != "직책 전체" and u.get("position_name") != position:
            continue
        if active == "활성" and not u.get("is_active"):
            continue
        if active == "비활성" and u.get("is_active"):
            continue
        result.append(u)
    return result


def _render_user_header(user: dict[str, Any]) -> None:
    st.button("← 계정 목록",key="hw_admin_back_users",on_click=_back_to_accounts)
    name = str(user.get("display_name") or user.get("login_id") or "사용자")
    initial = html.escape(name[:2].upper())
    state_chip = _chip("활성 계정", "good") if user.get("is_active") else _chip("비활성 계정", "off")
    role = _ROLE_LABELS.get(str(user.get("system_role_code") or "user"), str(user.get("system_role_name") or "일반 사용자"))
    st.markdown(
        f"""
        <div class="hw-profile-card">
          <div class="hw-profile-avatar">{initial}</div>
          <div style="flex:1">
            <div style="display:flex;align-items:center;gap:9px"><span class="hw-profile-name">{html.escape(name)}</span>{state_chip}</div>
            <div class="hw-profile-meta">{html.escape(str(user.get('login_id') or '-'))} · {html.escape(str(user.get('organization_name') or '-'))} · {html.escape(str(user.get('position_name') or '-'))} · {html.escape(role)}</div>
          </div>
          <div style="text-align:right"><div style="font-size:10px;color:#8b9aaa">최근 로그인</div><div style="font-size:12px;font-weight:800;color:#425c73;margin-top:4px">{html.escape(_fmt_relative(user.get('last_login_at')))}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _apply_user_changes(auth: HwarangAuthService, actor_id: str, uid: str, changes: dict[str, Any]) -> None:
    updated = auth.admin_apply_user_changes(actor_user_id=actor_id, target_user_id=uid, **changes)
    if uid == actor_id:
        from modules.shared.identity_state import reconcile_identity
        previous = st.session_state.get("hwarang_auth") or {}
        state = dict(previous)
        state.update(profile=updated["profile"], app_access=updated["app_access"],
                     feature_permissions=updated["feature_permissions"], profile_checked_at=0)
        reconcile_identity(st.session_state, previous, state)
        st.session_state.update(hwarang_auth=state, login_profile=updated["profile"],
                                password_correct=True, login_user=auth.workspace_permission_role(updated['profile']),
                                hw_app_access=updated["app_access"], hw_feature_permissions=set(updated["feature_permissions"]))
    st.session_state.pop("hw_admin_reference_cache", None); _clear_admin_read_cache()
    st.success("계정과 권한을 저장했습니다.")
    if uid == actor_id:
        st.rerun()  # Re-evaluate the shell and access after self-permission changes.
    refresh_current()


def _user_permissions(auth: HwarangAuthService, actor_id: str, uid: str) -> None:
    snapshot = auth.admin_user_snapshot(actor_id, uid)
    refs = _cached_reference_data(auth, actor_id)
    profile = snapshot["profile"]
    current_access = dict(snapshot.get("app_access") or {})
    current_permissions = set(snapshot.get("feature_permissions") or ())

    positions = [r for r in refs.get("positions", []) if r.get("is_active", True)]
    orgs = [r for r in refs.get("organizations", []) if r.get("is_active", True)]
    perms = [item for item in refs.get("permissions", []) if item.get("permission_code") not in _SIMULATOR_PERMISSIONS]
    st.markdown('<div class="hw-section-head">기본 정보</div>', unsafe_allow_html=True)
    from .organization_picker import render_affiliation, valid_affiliation, render_managers
    position_code, organization_unit_id = render_affiliation(orgs, positions, profile, 'hw_affiliation_'+uid)
    managers = render_managers(auth, actor_id, uid, organization_unit_id, 'hw_managers_'+uid)
    with st.form(f"hw_admin_user_permissions_v2_{uid}", clear_on_submit=False):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            display_name = st.text_input("이름", value=str(profile.get("display_name") or ""))
            current_role = str(profile.get("role") or "user")
            role_codes = list(_ROLE_LABELS)
            role = st.selectbox(
                "시스템 권한",
                role_codes,
                index=role_codes.index(current_role) if current_role in role_codes else 0,
                format_func=lambda x: _ROLE_LABELS[x],
            )
            is_active = st.toggle("계정 활성", value=bool(profile.get("is_active")))
        with c2:
            st.text_input("로그인 ID", value=str(profile.get("login_id") or ""), disabled=True)

        st.markdown("##### 앱 접근")
        app_values: dict[str, bool] = {}
        cols = st.columns(3)
        for col, code in zip(cols, ("workspace", "calculator", "academy")):
            with col:
                app_values[code] = st.toggle(
                    _APP_LABELS[code],
                    value=bool(current_access.get(code, False)),
                    key=f"hw_detail_app_v2_{uid}_{code}",
                )

        st.markdown("##### 세부 기능 권한")
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in perms:
            grouped[str(item.get("app_code") or "기타")].append(item)
        permission_values: dict[str, bool] = {}
        for app_code in ("workspace", "calculator", "academy"):
            items = grouped.get(app_code, [])
            if not items:
                continue
            allowed_count = sum(1 for i in items if str(i.get("permission_code")) in current_permissions)
            with st.expander(
                f"{_APP_LABELS.get(app_code, app_code)} · 현재 {allowed_count}/{len(items)} 허용",
                expanded=(app_code == "academy"),
            ):
                cols = st.columns(2)
                for idx, item in enumerate(items):
                    code = str(item["permission_code"])
                    with cols[idx % 2]:
                        permission_values[code] = st.toggle(
                            str(item.get("display_name") or code),
                            value=code in current_permissions,
                            key=f"hw_detail_perm_v2_{uid}_{code}",
                            help=str(item.get("description") or "") or None,
                        )

        submitted = st.form_submit_button("변경사항 저장", type="primary", use_container_width=True)

    if submitted:
        if not valid_affiliation(position_code, organization_unit_id, orgs):
            st.error('직책에 맞는 소속을 선택해 주세요.'); return
        changes = {
            "display_name": display_name,
            "role": role,
            "is_active": bool(is_active),
            "organization_unit_id": organization_unit_id,
            "position_code": position_code,
            **managers,
            "app_access": app_values,
            "permissions": permission_values,
        }
        dangerous = (
            role != current_role
            or bool(is_active) != bool(profile.get("is_active"))
            or not bool(app_values.get("workspace"))
        )
        if dangerous:
            st.session_state[f"hw_pending_danger_user_{uid}"] = changes
        else:
            _apply_user_changes(auth, actor_id, uid, changes)

    pending_key = f"hw_pending_danger_user_{uid}"
    pending = st.session_state.get(pending_key)
    if pending:
        st.warning("시스템 권한·계정 상태 또는 WORKSPACE 접근이 변경됩니다. 한 번 더 확인해 주세요.")
        c1, c2 = st.columns(2)
        if c1.button("취소", key=f"hw_cancel_danger_{uid}", use_container_width=True):
            st.session_state.pop(pending_key, None)
            refresh_current()
        if c2.button("위험 변경 적용", key=f"hw_apply_danger_{uid}", type="primary", use_container_width=True):
            st.session_state.pop(pending_key, None)
            _apply_user_changes(auth, actor_id, uid, pending)


def _render_activity(auth: HwarangAuthService, actor_id: str) -> None:
    """Legacy route compatibility: show only state-changing admin audit."""
    users=_fetch_users(auth); user_map={str(u.get("user_id")):u for u in users}; logs=auth.admin_audit_log(actor_id,limit=200)
    table=[{"시간":_fmt_dt(r.get("created_at")),"관리자":(user_map.get(str(r.get("actor_user_id"))) or {}).get("display_name") or r.get("actor_user_id"),"대상":(user_map.get(str(r.get("target_user_id"))) or {}).get("display_name") or r.get("target_user_id") or "-","작업":_ADMIN_ACTION_LABELS.get(str(r.get("action") or ""),str(r.get("action") or "-"))} for r in logs]
    st.dataframe(table,hide_index=True,use_container_width=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@st.fragment
def render(auth: HwarangAuthService) -> None:
    _inject_css()
    try:
        actor_id, _viewer = _require_actor(auth)
    except HwarangAuthError as exc:
        st.error(str(exc))
        return

    page = str(st.session_state.setdefault("hw_admin_center_page", "dashboard"))
    if page not in _PAGE_LABELS or (page not in {"dashboard", "operations", "accounts"} and not _simulator_available()):
        page = "dashboard"
        st.session_state["hw_admin_center_page"] = page

    from modules.shell.page_slot import page_slot
    with page_slot('admin:'+page):
        _top_header(page)
        try:
            if page == "dashboard":
                _render_dashboard(auth, actor_id)
            elif page == "operations":
                from modules.shared.operations_ui import render as render_operations
                render_operations(auth, actor_id)
            elif page == "accounts":
                _render_accounts(auth, actor_id)
            else:
                from . import simulator_admin_ui
                simulator_admin_ui.render(page, auth, actor_id)
        except HwarangAuthError as exc:
            st.error(str(exc))
