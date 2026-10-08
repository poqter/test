"""HWARANG PLATFORM · Super Admin Center V2.

The console is intentionally task-oriented rather than a raw Streamlit admin
page: dashboard alerts, account/permission management, ACADEMY operations,
AI FinOps, credit policy, and a separated danger zone live in one shell.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import html
import time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from modules.shared.ai_guardrails import (
    credit_display_state,
    get_training_credit_status,
    training_credit_display_state,
    voice_display_state,
)
from modules.shared.external_apps import academy_url, calculator_url
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService


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
_ASSET_SOURCE_LABELS = {
    "purchase": "구매",
    "promotion_reward": "프로모션·보상",
    "bonus": "프로모션·보상",  # legacy row compatibility
    "admin_adjustment": "관리자 조정",
    "migration": "이관",
    "system": "시스템",
}
_ASSET_OPERATION_LABELS = {
    "grant": "추가",
    "revoke": "차감",
    "reset": "직접 설정",
}
_ASSET_TYPE_LABELS = {
    "training_credit": "훈련 크레딧",
    "voice": "Voice",
}
_UNIT_LABELS = {
    "root": "전체",
    "head_unit": "본부/직할",
    "branch": "지점/직할",
    "team": "팀",
}
_PAGE_LABELS = {
    "dashboard": "대시보드",
    "accounts": "계정 · 권한",
    "academy": "ACADEMY 관리",
    "ai": "AI 사용량 · 비용",
    "settings": "시스템 설정",
}
_PAGE_SUBTITLES = {
    "dashboard": "플랫폼 운영 상태와 지금 확인해야 할 항목을 한눈에 봅니다.",
    "accounts": "사용자 계정, 앱 접근권한, 세부 기능권한과 이용량을 관리합니다.",
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
    return rows if isinstance(rows, list) else []


def _safe_rpc(auth: HwarangAuthService, path: str, payload: dict[str, Any]) -> Any:
    result = auth._request("POST", f"/rest/v1/rpc/{path}", admin=True, json=payload)
    # Only successful writes invalidate reads; failed writes keep the last
    # confirmed state. RPCs here retain the existing server Audit/Ledger logic.
    _clear_admin_read_cache()
    st.session_state.pop("hw_admin_reference_cache", None)
    return result


_ADMIN_READ_CACHE_KEY = "hw_admin_read_cache_v1"


def _operations_summary(auth: HwarangAuthService) -> dict | None:
    actor = str((st.session_state.get('login_profile') or {}).get('id') or '')
    if not actor:
        return None
    key = f'operations:{actor}:{datetime.now(_KST).date()}'
    def load():
        try:
            value = auth._request('POST', '/rest/v1/rpc/get_hwarang_admin_operations_summary',
                                  admin=True, json={'p_actor_user_id': actor})
            return value if isinstance(value, dict) and isinstance(value.get('ai'), dict) else None
        except HwarangAuthError:
            return None
    return _cached_admin_read(key, 30, load)


def _statistics_status(summary: dict | None, key: str) -> None:
    col, action = st.columns([5, 1])
    if summary:
        col.caption('전체 기록 집계 · KST · 마지막 갱신 ' + _fmt_dt(summary.get('updated_at')))
    else:
        col.caption('통계 집계 연결 전: 아래 값은 불러온 기록 기준입니다.')
    action.button('새로고침', key=key, on_click=_clear_admin_read_cache, use_container_width=True)

def _cached_admin_read(cache_key: str, ttl_seconds: int, loader):
    """Cache short-lived admin read results within the current Streamlit session."""
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
    cache[str(cache_key)] = {"at": now, "data": data}
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


def _fetch_users(auth: HwarangAuthService) -> list[dict[str, Any]]:
    rows = _cached_admin_read("reference:users", 15, lambda: _safe_rows(
        auth,
        "/rest/v1/hwarang_admin_user_operations_view",
        params={"select": "*", "order": "display_name.asc.nullslast,login_id.asc"},
    ))
    return rows


def _fetch_runtime(auth: HwarangAuthService) -> dict[str, Any]:
    rows = _cached_admin_read("reference:runtime", 30, lambda: _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_runtime_config",
        params={"select": "*", "config_id": "eq.1", "limit": "1"},
    ))
    return rows[0] if rows else {}


def _fetch_credit_policy(auth: HwarangAuthService) -> dict[str, Any]:
    rows = _cached_admin_read("reference:credit_policy", 30, lambda: _safe_rows(
        auth,
        "/rest/v1/hwarang_credit_policy",
        params={"select": "*", "config_id": "eq.1", "limit": "1"},
    ))
    return rows[0] if rows else {
        "monthly_free_credits": 1000,
        "remaining_warning_percent": 20,
        "default_voice_minutes": 0,
        "monthly_ai_budget_usd": 50,
        "budget_warning_percent": 80,
    }


def _cached_reference_data(auth: HwarangAuthService, actor_id: str) -> dict[str, list[dict[str, Any]]]:
    key = "hw_admin_reference_cache"
    cached = st.session_state.get(key)
    now = time.time()
    if isinstance(cached, dict) and now - float(cached.get("at") or 0) < 60:
        return dict(cached.get("data") or {})
    data = auth.admin_reference_data(actor_id)
    st.session_state[key] = {"at": now, "data": data}
    return data


def _page_change(page: str) -> None:
    st.session_state["hw_admin_center_page"] = page
    if page != "accounts": st.session_state.pop("hw_admin_selected_user_id", None)

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
            ("운영", [("dashboard", "대시보드"), ("accounts", "계정 · 권한")]),
            ("ACADEMY", [("academy", "학습 운영")]),
            ("AI", [("ai", "사용량 · 비용")]),
            ("시스템", [("settings", "시스템 설정")]),
        ]
        for group, items in groups:
            st.caption(group)
            for code, label in items:
                st.button(label,key=f"hw_admin_nav_{code}",type="primary" if current==code else "secondary",use_container_width=True,on_click=_page_change,args=(code,))
            st.write("")

        st.divider()
        st.button("← WORKSPACE로 돌아가기",key="hw_admin_exit",use_container_width=True,on_click=_exit_admin_center)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def _render_dashboard(auth: HwarangAuthService, actor_id: str) -> None:
    operations = _operations_summary(auth)
    _statistics_status(operations, "hw_dashboard_refresh")
    users = _fetch_users(auth)
    runtime = _fetch_runtime(auth)
    policy = _fetch_credit_policy(auth)

    recent_logins=_cached_admin_read("dashboard:recent_logins",15,lambda:_safe_rows(auth,"/rest/v1/hwarang_activity_log",params={"select":"id,user_id,app_code,created_at","event_code":"eq.LOGIN_SUCCESS","order":"created_at.desc","limit":"12"}))
    sessions=_cached_admin_read("dashboard:academy_sessions",15,lambda:_safe_rows(auth,"/rest/v1/academy_sessions",params={"select":"id,user_id,status,stage,mode,interaction_mode,updated_at,started_at","order":"updated_at.desc","limit":"200"}))
    ai_month = _cached_admin_read(
        "dashboard:ai_month",30,lambda:_safe_rows(auth,"/rest/v1/hwarang_admin_ai_usage_daily_view",params={
            "select":"usage_day,user_id,ai_role,model,request_count,credits_charged,calculated_cost_usd",
            "usage_day":"gte."+_month_start_utc_iso(),"order":"usage_day.desc","limit":"1000"})) if operations is None else []
    ai_today = [r for r in ai_month if _logged_in_today(r.get("usage_day"))]
    requests_24h=_cached_admin_read("dashboard:requests_24h",15,lambda:_safe_rows(auth,"/rest/v1/hwarang_ai_request_registry",params={"select":"user_id,status,block_reason,purpose,created_at","created_at":"gte."+_last_24h_utc_iso(),"order":"created_at.desc","limit":"500"}))

    total_users = len(users)
    today_logins = sum(1 for u in users if _logged_in_today(u.get("last_login_at")))
    in_progress = [s for s in sessions if s.get("status") == "in_progress"]
    today_cost = float(operations["ai"]["today_cost"]) if operations else sum(float(r.get("calculated_cost_usd") or 0) for r in ai_today)

    cols = st.columns(4, gap="medium")
    with cols[0]:
        _metric_card("전체 사용자", f"{total_users:,}", f"활성 {sum(1 for u in users if u.get('is_active')):,}")
    with cols[1]:
        _metric_card("오늘 로그인", f"{today_logins:,}", "KST 기준 고유 사용자")
    with cols[2]:
        voice_now = sum(1 for s in in_progress if s.get("interaction_mode") == "VOICE")
        active_count = int(operations["academy"]["in_progress"]) if operations else len(in_progress)
        voice_now = int(operations["academy"]["voice_in_progress"]) if operations else voice_now
        _metric_card("진행 중 ACADEMY", f"{active_count:,}", f"Voice {voice_now:,}")
    with cols[3]:
        _metric_card("오늘 학습 AI 예상비용", f"${today_cost:,.2f}", "상담 훈련·평가·Voice 사용 기록")

    st.write("")
    left, right = st.columns([1.08, .92], gap="large")

    with left:
        st.markdown('<div class="hw-section-head">조치 필요</div>', unsafe_allow_html=True)
        low_training = [
            u for u in users
            if int(u.get("monthly_grant_credits") or 0) > 0
            and int(u.get("training_credit_available") or 0) <= int(u.get("training_warning_threshold") or 0)
        ]
        remaining_warning = int(policy.get("remaining_warning_percent") or 20)
        low_voice = []
        for u in users:
            alloc = int(u.get("voice_allocation_seconds") or 0)
            available = max(0, int(u.get("voice_balance_seconds") or 0) - int(u.get("voice_reserved_seconds") or 0))
            if alloc > 0 and (available / alloc * 100) <= remaining_warning:
                low_voice.append(u)
        failed = [r for r in requests_24h if r.get("status") in ("blocked", "failed") or r.get("block_reason")]
        inactive = [u for u in users if not u.get("is_active")]
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stale = []
        for s in in_progress:
            try:
                dt = datetime.fromisoformat(str(s.get("updated_at") or "").replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < stale_cutoff:
                    stale.append(s)
            except Exception:
                pass

        alerts = [
            ("high", "AI 요청 실패·차단", len(failed), "최근 24시간", "ai"),
            ("medium", f"훈련 크레딧 잔여 {remaining_warning}% 이하", len(low_training), "사용자", "accounts"),
            ("medium", f"Voice 잔여 {remaining_warning}% 이하", len(low_voice), "사용자", "accounts"),
            ("medium", "24시간 이상 미종료 Session", len(stale), "Session", "academy"),
            ("low", "비활성 계정", len(inactive), "계정", "accounts"),
        ]
        visible = [x for x in alerts if x[2] > 0]
        if not visible:
            st.success("현재 확인이 필요한 운영 이슈가 없습니다.")
        else:
            for idx, (priority, title, count, unit, target) in enumerate(visible):
                c1, c2 = st.columns([4, 1], vertical_alignment="center")
                with c1:
                    st.markdown(
                        f"""
                        <div class="hw-alert">
                          <div><strong>{html.escape(title)}</strong><small>{count:,}{html.escape(unit)} 확인 필요</small></div>
                          <span class="hw-alert-priority {priority}">{priority.upper()}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("확인", key=f"hw_alert_{idx}_{target}", use_container_width=True):
                        _page_change(target)

        st.markdown('<div class="hw-section-head">최근 로그인</div>', unsafe_allow_html=True)
        user_map = {str(u.get("user_id")): u for u in users}
        table = []
        for row in recent_logins:
            user = user_map.get(str(row.get("user_id")), {})
            table.append({
                "시간": _fmt_relative(row.get("created_at")),
                "사용자": user.get("display_name") or user.get("login_id") or "-",
                "로그인 앱": _APP_LABELS.get(str(row.get("app_code") or ""), str(row.get("app_code") or "").upper()),
            })
        if table:
            st.dataframe(table, hide_index=True, use_container_width=True)
        else:
            st.caption("아직 로그인 기록이 없습니다.")

    with right:
        st.markdown('<div class="hw-section-head">운영 상태</div>', unsafe_allow_html=True)
        academy_configured = bool(academy_url())
        calculator_configured = bool(calculator_url())
        st.markdown(
            f"""
            <div class="hw-admin-card">
              <div class="hw-status-row"><span class="hw-status-label">WORKSPACE</span>{_chip('운영 중','good')}</div>
              <div class="hw-status-row"><span class="hw-status-label">ACADEMY</span>{_chip('연결 구성' if academy_configured else '주소 미설정','good' if academy_configured else 'warn')}</div>
              <div class="hw-status-row"><span class="hw-status-label">CALCULATOR</span>{_chip('연결 구성' if calculator_configured else '주소 미설정','good' if calculator_configured else 'warn')}</div>
              <div class="hw-status-row"><span class="hw-status-label">AI 서비스</span>{_chip('ON' if runtime.get('service_enabled') else 'OFF','good' if runtime.get('service_enabled') else 'off')}</div>
              <div class="hw-status-row"><span class="hw-status-label">Text AI</span>{_chip('ON' if runtime.get('text_enabled') else 'OFF','good' if runtime.get('text_enabled') else 'off')}</div>
              <div class="hw-status-row"><span class="hw-status-label">Voice AI</span>{_chip('ON' if runtime.get('voice_enabled') else 'OFF','good' if runtime.get('voice_enabled') else 'off')}</div>
              <div class="hw-status-row"><span class="hw-status-label">AI 정식평가</span>{_chip('ON' if runtime.get('assessment_enabled') else 'OFF','good' if runtime.get('assessment_enabled') else 'off')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="hw-section-head">이번 달 학습 AI 예산</div>', unsafe_allow_html=True)
        month_cost = float(operations["ai"]["month_cost"]) if operations else sum(float(r.get("calculated_cost_usd") or 0) for r in ai_month)
        budget = float(policy.get("monthly_ai_budget_usd") or 0)
        budget_warning = int(policy.get("budget_warning_percent") or 80)
        if budget > 0:
            ratio = month_cost / budget * 100
            st.progress(min(1.0, max(0.0, ratio / 100)))
            st.caption(f"USD {month_cost:,.2f} / USD {budget:,.2f} · {ratio:.1f}% 사용")
            if ratio >= budget_warning:
                st.warning(f"월 AI 예산의 {budget_warning}% 이상을 사용했습니다.")
        else:
            st.caption("월 AI 예산 경고가 비활성화되어 있습니다.")

        st.markdown('<div class="hw-section-head">현재 ACADEMY</div>', unsafe_allow_html=True)
        if in_progress:
            user_map = {str(u.get("user_id")): u for u in users}
            for s in in_progress[:8]:
                user = user_map.get(str(s.get("user_id")), {})
                st.caption(
                    f"{user.get('display_name') or user.get('login_id') or '사용자'} · "
                    f"{s.get('stage') or '-'} · {s.get('mode') or '-'} · "
                    f"{s.get('interaction_mode') or 'TEXT'} · {_fmt_relative(s.get('updated_at'))}"
                )
        else:
            st.caption("현재 진행 중인 ACADEMY Session이 없습니다.")


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


def _render_accounts(auth: HwarangAuthService, actor_id: str) -> None:
    users = _fetch_users(auth)
    selected_id = st.session_state.get("hw_admin_selected_user_id")
    if selected_id:
        selected = next((u for u in users if str(u.get("user_id")) == str(selected_id)), None)
        if selected:
            _render_user_detail(auth, actor_id, selected)
            return
        st.session_state.pop("hw_admin_selected_user_id", None)

    filtered = _account_filters(users)
    st.caption(
        f"총 {len(filtered):,}명 · 표에서 여러 계정을 선택하거나 현재 검색 결과 전체를 대상으로 훈련 크레딧·Voice를 일괄 처리할 수 있습니다."
    )
    table: list[dict[str, Any]] = []
    for u in filtered:
        total_credit = int(u.get("training_credit_available") or 0)
        voice_available = max(0, int(u.get("voice_balance_seconds") or 0) - int(u.get("voice_reserved_seconds") or 0))
        table.append({
            "사용자": f"{u.get('display_name') or '-'} · {u.get('login_id') or '-'}",
            "소속": u.get("organization_name") or "-",
            "직책": u.get("position_name") or "-",
            "계정": "활성" if u.get("is_active") else "비활성",
            "최근 접속": _fmt_relative(u.get("last_login_at")),
            "ACADEMY": "사용 가능" if u.get("academy_access") else "제한",
            "훈련 크레딧": f"{total_credit:,}",
            "Voice": f"{voice_available / 60:.0f}분" if int(u.get("voice_allocation_seconds") or 0) > 0 else "미지급",
        })

    if not table:
        st.info("조건에 맞는 계정이 없습니다.")
        return

    event = st.dataframe(
        pd.DataFrame(table),
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="multi-row",
        key="hw_admin_user_table_v2",
    )
    try:
        selected_rows = [int(i) for i in event.selection.rows]
    except Exception:
        selected_rows = []
    selected_users = [filtered[i] for i in selected_rows if 0 <= i < len(filtered)]

    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    with c1:
        if len(selected_users) == 1 and st.button("선택 계정 상세", type="primary", use_container_width=True):
            st.session_state["hw_admin_selected_user_id"] = str(selected_users[0]["user_id"])
            st.session_state["hw_admin_user_page"] = "overview"
            st.rerun()
    with c2:
        if selected_users:
            st.caption(f"표에서 {len(selected_users)}명 선택됨")
        else:
            st.caption("개별 계정은 표의 행을 선택한 뒤 상세 화면에서 수정할 수 있습니다.")

    use_filtered = st.checkbox(
        f"현재 검색 결과 전체 {len(filtered):,}명을 일괄 처리 대상으로 사용",
        value=False,
        key="hw_admin_bulk_use_filtered_v4",
        help="소속·직책·상태·검색어 필터가 적용된 현재 결과 전체가 대상이 됩니다.",
    )
    bulk_users = filtered if use_filtered else selected_users

    if bulk_users:
        with st.expander(f"선택 사용자 자산 일괄 처리 · 대상 {len(bulk_users):,}명", expanded=False):
            asset_type = st.radio(
                "처리 자산",
                ["training_credit", "voice"],
                horizontal=True,
                format_func=lambda x: _ASSET_TYPE_LABELS[x],
                key="hw_admin_bulk_asset_type_v4",
            )
            is_voice = asset_type == "voice"
            unit = "분" if is_voice else "Credit"
            default_amount = 30 if is_voice else 500
            step_amount = 10 if is_voice else 100

            with st.form("hw_admin_bulk_asset_v4"):
                b1, b2, b3 = st.columns([1, 1, 1])
                operation = b1.selectbox(
                    "처리 방식",
                    ["grant", "revoke", "reset"],
                    format_func=lambda x: _ASSET_OPERATION_LABELS[x],
                )
                source_type = b2.selectbox(
                    "처리 구분",
                    ["purchase", "promotion_reward", "admin_adjustment"],
                    format_func=lambda x: _ASSET_SOURCE_LABELS[x],
                )
                amount = b3.number_input(
                    f"1인당 {unit}",
                    min_value=0,
                    value=default_amount,
                    step=step_amount,
                    help="추가·차감은 1 이상, 직접 설정은 0도 가능합니다.",
                )
                note = st.text_input(
                    "사유",
                    placeholder=(
                        "예: Voice 추가 구매 / 교육 보상 / 관리자 보정"
                        if is_voice else
                        "예: 추가 크레딧 구매 / 교육 프로모션 / 관리자 보정"
                    ),
                )
                preview = st.form_submit_button("적용 내용 미리보기", type="primary", use_container_width=True)

            if preview:
                if operation in ("grant", "revoke") and int(amount) <= 0:
                    st.error("추가·차감 처리 수량은 1 이상이어야 합니다.")
                else:
                    st.session_state["hw_admin_bulk_asset_pending_v4"] = {
                        "user_ids": [str(u["user_id"]) for u in bulk_users],
                        "user_names": [str(u.get("display_name") or u.get("login_id") or u.get("user_id")) for u in bulk_users],
                        "asset_type": asset_type,
                        "operation": operation,
                        "source_type": source_type,
                        "amount": int(amount),
                        "note": note.strip(),
                    }

    pending = st.session_state.get("hw_admin_bulk_asset_pending_v4")
    if pending:
        target_count = len(pending.get("user_ids") or [])
        amount_each = int(pending.get("amount") or 0)
        asset_type = str(pending.get("asset_type") or "training_credit")
        operation = str(pending.get("operation") or "grant")
        source_type = str(pending.get("source_type") or "admin_adjustment")
        asset_label = _ASSET_TYPE_LABELS.get(asset_type, asset_type)
        unit = "분" if asset_type == "voice" else "Credit"
        names = list(pending.get("user_names") or [])
        sample_names = ", ".join(names[:5]) + (f" 외 {len(names) - 5}명" if len(names) > 5 else "")

        st.markdown('<div class="hw-section-head">일괄 처리 최종 확인</div>', unsafe_allow_html=True)
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("대상", f"{target_count:,}명")
        p2.metric("자산", asset_label)
        p3.metric("처리", _ASSET_OPERATION_LABELS.get(operation, operation))
        p4.metric("구분", _ASSET_SOURCE_LABELS.get(source_type, source_type))
        p5.metric("1인당", f"{amount_each:,}{unit}")
        if operation in ("grant", "revoke"):
            st.caption(f"총 처리량 {amount_each * target_count:,}{unit} · {sample_names}")
        else:
            st.caption(f"각 계정의 {asset_label} 잔액을 {amount_each:,}{unit}로 직접 설정 · {sample_names}")
        if pending.get("note"):
            st.caption(f"사유 · {pending['note']}")
        if operation in ("revoke", "reset"):
            reservation_label = "Voice" if asset_type == "voice" else "구매/추가 크레딧"
            st.warning(f"차감·직접 설정은 예약 중인 {reservation_label}가 있는 계정에서 실패할 수 있습니다. 실패 계정은 결과에 따로 표시됩니다.")

        c1, c2 = st.columns(2)
        if c1.button("일괄 처리 취소", key="hw_admin_bulk_asset_cancel_v4", use_container_width=True):
            st.session_state.pop("hw_admin_bulk_asset_pending_v4", None)
            st.rerun()
        if c2.button(
            f"{target_count:,}명에게 적용",
            key="hw_admin_bulk_asset_apply_v4",
            type="primary",
            use_container_width=True,
        ):
            if asset_type == "voice":
                rpc_name = "admin_bulk_adjust_hwarang_voice_minutes"
                payload = {
                    "p_actor_user_id": actor_id,
                    "p_target_user_ids": pending["user_ids"],
                    "p_operation": operation,
                    "p_minutes": amount_each,
                    "p_source_type": source_type,
                    "p_note": pending.get("note") or None,
                }
            else:
                rpc_name = "admin_bulk_adjust_hwarang_purchased_credits"
                payload = {
                    "p_actor_user_id": actor_id,
                    "p_target_user_ids": pending["user_ids"],
                    "p_operation": operation,
                    "p_amount": amount_each,
                    "p_source_type": source_type,
                    "p_note": pending.get("note") or None,
                }

            result = _safe_rpc(auth, rpc_name, payload)
            if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
                result = result[0]
            result = result if isinstance(result, dict) else {}
            success_count = int(result.get("success_count") or 0)
            failed_count = int(result.get("failed_count") or 0)
            st.session_state.pop("hw_admin_bulk_asset_pending_v4", None)

            if failed_count:
                st.warning(f"일괄 처리 결과 · 성공 {success_count:,}명 / 실패 {failed_count:,}명")
                failures = []
                failed_ids = []
                failed_names = []
                name_map = dict(zip(pending["user_ids"], pending["user_names"]))
                for row in result.get("results") or []:
                    if row.get("status") == "failed":
                        uid = str(row.get("user_id") or "")
                        display_name = name_map.get(uid, uid)
                        failed_ids.append(uid)
                        failed_names.append(display_name)
                        failures.append({
                            "사용자": display_name,
                            "실패 사유": row.get("error") or "처리 실패",
                        })
                if failures:
                    st.dataframe(failures, hide_index=True, use_container_width=True)
                    st.session_state["hw_admin_bulk_asset_retry_v4"] = {
                        "user_ids": failed_ids,
                        "user_names": failed_names,
                        "asset_type": asset_type,
                        "operation": operation,
                        "source_type": source_type,
                        "amount": amount_each,
                        "note": pending.get("note") or "",
                    }
            else:
                st.session_state.pop("hw_admin_bulk_asset_retry_v4", None)
                st.success(f"{success_count:,}명의 {asset_label} 일괄 처리가 완료되었습니다.")

    retry = st.session_state.get("hw_admin_bulk_asset_retry_v4")
    if retry and retry.get("user_ids"):
        if st.button(
            f"실패 {len(retry['user_ids']):,}명만 다시 처리",
            key="hw_admin_bulk_asset_retry_button_v4",
            use_container_width=True,
        ):
            st.session_state["hw_admin_bulk_asset_pending_v4"] = retry
            st.session_state.pop("hw_admin_bulk_asset_retry_v4", None)
            st.rerun()

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


def _render_user_detail(auth: HwarangAuthService, actor_id: str, user: dict[str, Any]) -> None:
    _render_user_header(user)
    current = st.session_state.setdefault("hw_admin_user_page", "overview")
    page = st.segmented_control(
        "사용자 상세",
        ["overview", "permissions", "academy", "ai"],
        default=current,
        format_func=lambda x: {
            "overview": "개요",
            "permissions": "권한",
                    "academy": "ACADEMY",
            "ai": "AI 이용량",
        }[x],
        key="hw_admin_user_nav_v2",
        label_visibility="collapsed",
    ) or current
    st.session_state["hw_admin_user_page"] = page

    uid = str(user["user_id"])
    if page == "overview":
        _user_overview(auth, uid, user)
    elif page == "permissions":
        _user_permissions(auth, actor_id, uid)
    elif page == "academy":
        _user_academy(auth, uid)
    else:
        _user_ai(auth, actor_id, uid)


def _user_overview(auth: HwarangAuthService, uid: str, user: dict[str, Any]) -> None:
    since=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
    sessions=_safe_rows(auth,"/rest/v1/academy_sessions",params={"select":"id,status,mode,stage,interaction_mode,started_at,ended_at","user_id":f"eq.{uid}","started_at":"gte."+since,"order":"started_at.desc","limit":"200"})
    credit=get_training_credit_status(auth,uid)
    cols=st.columns(4); cols[0].metric("최근 로그인",_fmt_relative(user.get("last_login_at"))); cols[1].metric("ACADEMY Session",len(sessions)); cols[2].metric("완료 Session",sum(1 for row in sessions if row.get("status")=="completed")); cols[3].metric("훈련 크레딧",f"{credit.available_credits:,}" if credit else "-")
    if credit:
        st.markdown('<div class="hw-section-head">크레딧 구성</div>',unsafe_allow_html=True); c1,c2,c3=st.columns(3); c1.metric("이번 달 기본",f"{credit.monthly_available_credits:,}"); c2.metric("구매/추가",f"{credit.purchased_available_credits:,}"); c3.metric("Voice",f"{credit.voice_available_seconds/60:.0f}분"); st.caption("월 기본 크레딧이 먼저 사용되며 구매/추가 크레딧은 만료되지 않습니다.")


def _apply_user_changes(auth: HwarangAuthService, actor_id: str, uid: str, changes: dict[str, Any]) -> None:
    auth.admin_apply_user_changes(actor_user_id=actor_id, target_user_id=uid, **changes)
    st.session_state.pop("hw_admin_reference_cache", None); _clear_admin_read_cache()
    st.success("계정과 권한을 저장했습니다.")
    st.rerun()


def _user_permissions(auth: HwarangAuthService, actor_id: str, uid: str) -> None:
    snapshot = auth.admin_user_snapshot(actor_id, uid)
    refs = _cached_reference_data(auth, actor_id)
    profile = snapshot["profile"]
    current_access = dict(snapshot.get("app_access") or {})
    current_permissions = set(snapshot.get("feature_permissions") or ())

    positions = [r for r in refs.get("positions", []) if r.get("is_active", True)]
    orgs = [r for r in refs.get("organizations", []) if r.get("is_active", True)]
    perms = list(refs.get("permissions", []))
    pos_codes = [str(r["code"]) for r in positions]
    pos_labels = {str(r["code"]): str(r.get("display_name") or r["code"]) for r in positions}
    org_ids = [str(r["id"]) for r in orgs]
    org_labels = {
        str(r["id"]): f"{r.get('name') or r.get('code')} · {_UNIT_LABELS.get(str(r.get('unit_type') or ''), r.get('unit_type') or '')}"
        for r in orgs
    }

    st.markdown('<div class="hw-section-head">기본 정보</div>', unsafe_allow_html=True)
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
            current_org = str(profile.get("organization_unit_id") or "")
            organization_unit_id = st.selectbox(
                "소속",
                org_ids,
                index=org_ids.index(current_org) if current_org in org_ids else 0,
                format_func=lambda x: org_labels.get(x, x),
            ) if org_ids else None
            current_pos = str(profile.get("position_code") or "fp")
            position_code = st.selectbox(
                "직책",
                pos_codes,
                index=pos_codes.index(current_pos) if current_pos in pos_codes else 0,
                format_func=lambda x: pos_labels.get(x, x),
            ) if pos_codes else current_pos
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
        changes = {
            "display_name": display_name,
            "role": role,
            "is_active": bool(is_active),
            "organization_unit_id": organization_unit_id,
            "position_code": position_code,
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
            st.rerun()
        if c2.button("위험 변경 적용", key=f"hw_apply_danger_{uid}", type="primary", use_container_width=True):
            st.session_state.pop(pending_key, None)
            _apply_user_changes(auth, actor_id, uid, pending)


def _user_academy(auth: HwarangAuthService, uid: str) -> None:
    sessions = _safe_rows(
        auth,
        "/rest/v1/academy_sessions",
        params={
            "select": "id,status,stage,scenario_id,mode,training_focus,interaction_mode,last_turn_no,started_at,ended_at,updated_at",
            "user_id": f"eq.{uid}",
            "order": "updated_at.desc",
            "limit": "200",
        },
    )
    display = []
    for r in sessions:
        display.append({
            "상태": r.get("status"),
            "훈련": "규칙 기반" if (r.get("metadata") or {}).get("training_engine") == "rules" else "AI/기타",
            "단계": r.get("stage"),
            "시나리오": r.get("scenario_id") or "-",
            "모드": r.get("mode") or "-",
            "Focus": r.get("training_focus") or "-",
            "방식": r.get("interaction_mode") or "TEXT",
            "Turn": r.get("last_turn_no") or 0,
            "시작": _fmt_dt(r.get("started_at")),
            "종료": _fmt_dt(r.get("ended_at")),
        })
    st.dataframe(display, hide_index=True, use_container_width=True)


def _user_ai(auth: HwarangAuthService, actor_id: str, uid: str) -> None:
    credit = get_training_credit_status(auth, uid)
    if not credit:
        st.info("Migration 13 적용 후 크레딧 관리가 활성화됩니다.")
        return

    label, _ = training_credit_display_state(credit)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 훈련 크레딧", f"{credit.available_credits:,}")
    c2.metric("이번 달 기본", f"{credit.monthly_available_credits:,}")
    c3.metric("구매/추가", f"{credit.purchased_available_credits:,}")
    c4.metric("상태", label)
    st.caption(
        f"{credit.monthly_credit_period or '-'} · 월 기본이 먼저 사용됩니다. "
        "구매/추가 크레딧은 월 변경으로 사라지지 않습니다."
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### 훈련 크레딧 조정")
        with st.form(f"hw_purchased_credit_{uid}"):
            operation = st.radio(
                "작업",
                ["grant", "revoke", "reset"],
                horizontal=True,
                format_func=lambda x: _ASSET_OPERATION_LABELS[x],
            )
            amount = st.number_input("크레딧", min_value=0, step=100, value=500)
            source_type = st.selectbox(
                "처리 구분",
                ["purchase", "promotion_reward", "admin_adjustment"],
                format_func=lambda x: _ASSET_SOURCE_LABELS[x],
            )
            note = st.text_input("사유", placeholder="예: 11월 추가 구매 / 교육 보상")
            submit = st.form_submit_button("훈련 크레딧 적용", type="primary", use_container_width=True)
        if submit:
            if operation in ("grant", "revoke") and int(amount) <= 0:
                st.error("추가·차감 처리 금액은 1 이상이어야 합니다.")
            else:
                _safe_rpc(
                    auth,
                    "admin_adjust_hwarang_purchased_credits",
                    {
                        "p_actor_user_id": actor_id,
                        "p_target_user_id": uid,
                        "p_operation": operation,
                        "p_amount": int(amount),
                        "p_source_type": source_type,
                        "p_note": note,
                    },
                )
                st.success("훈련 크레딧을 반영했습니다.")
                st.rerun()

    with right:
        st.markdown("##### Voice 조정")
        voice_label, _ = voice_display_state(
            credit.voice_remaining_percent,
            allocation_seconds=credit.voice_allocation_seconds,
            warning_percent=credit.remaining_warning_percent,
        )
        st.metric("잔여 Voice", f"{credit.voice_available_seconds / 60:.0f}분", voice_label)
        with st.form(f"hw_voice_credit_{uid}"):
            operation = st.radio(
                "작업",
                ["grant", "revoke", "reset"],
                horizontal=True,
                format_func=lambda x: _ASSET_OPERATION_LABELS[x],
                key=f"hw_voice_op_{uid}",
            )
            minutes = st.number_input("음성 이용량(분)", min_value=0, step=10, value=30, key=f"hw_voice_min_{uid}")
            voice_source_type = st.selectbox(
                "처리 구분",
                ["purchase", "promotion_reward", "admin_adjustment"],
                format_func=lambda x: _ASSET_SOURCE_LABELS[x],
                key=f"hw_voice_source_{uid}",
            )
            note = st.text_input("사유", placeholder="예: Voice 추가 구매 / 교육 보상", key=f"hw_voice_note_{uid}")
            submit_voice = st.form_submit_button("Voice 적용", type="primary", use_container_width=True)
        if submit_voice:
            if operation in ("grant", "revoke") and int(minutes) <= 0:
                st.error("추가·차감 Voice 시간은 1분 이상이어야 합니다.")
            else:
                _safe_rpc(
                    auth,
                    "admin_adjust_hwarang_voice_minutes",
                    {
                        "p_actor_user_id": actor_id,
                        "p_target_user_id": uid,
                        "p_operation": operation,
                        "p_minutes": int(minutes),
                        "p_source_type": voice_source_type,
                        "p_note": note,
                    },
                )
                st.success("Voice 이용량을 반영했습니다.")
                st.rerun()

    usage = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_usage_log",
        params={
            "select": "ai_role,model,input_tokens,cached_tokens,output_tokens,credits_charged,voice_seconds_charged,calculated_cost_usd,status,latency_ms,created_at",
            "user_id": f"eq.{uid}",
            "order": "created_at.desc",
            "limit": "200",
        },
    )
    credit_ledger = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_credit_ledger",
        params={
            "select": "entry_type,delta_credits,bucket,source_type,monthly_balance_after,purchased_balance_after,balance_after,note,credit_period,created_at",
            "user_id": f"eq.{uid}",
            "order": "created_at.desc",
            "limit": "300",
        },
    )
    voice_ledger = _safe_rows(
        auth,
        "/rest/v1/hwarang_voice_ledger",
        params={
            "select": "entry_type,delta_seconds,balance_after_seconds,allocation_after_seconds,source_type,note,created_at",
            "user_id": f"eq.{uid}",
            "order": "created_at.desc",
            "limit": "300",
        },
    )

    st.markdown('<div class="hw-section-head">AI 사용 원장</div>', unsafe_allow_html=True)
    if usage:
        st.dataframe(usage, hide_index=True, use_container_width=True)
    else:
        st.caption("아직 실제 AI 사용 기록이 없습니다.")

    st.markdown('<div class="hw-section-head">훈련 크레딧 원장</div>', unsafe_allow_html=True)
    if credit_ledger:
        credit_rows = [{
            "시간": _fmt_dt(r.get("created_at")),
            "처리": _ASSET_OPERATION_LABELS.get(str(r.get("entry_type") or ""), str(r.get("entry_type") or "-")),
            "구분": _ASSET_SOURCE_LABELS.get(str(r.get("source_type") or ""), str(r.get("source_type") or "-")),
            "변동": int(r.get("delta_credits") or 0),
            "구매/추가 잔액": int(r.get("purchased_balance_after") or 0),
            "전체 잔액": int(r.get("balance_after") or 0),
            "사유": r.get("note") or "-",
        } for r in credit_ledger]
        st.dataframe(credit_rows, hide_index=True, use_container_width=True)
    else:
        st.caption("크레딧 변동 기록이 없습니다.")

    st.markdown('<div class="hw-section-head">Voice 원장</div>', unsafe_allow_html=True)
    if voice_ledger:
        voice_rows = [{
            "시간": _fmt_dt(r.get("created_at")),
            "처리": _ASSET_OPERATION_LABELS.get(str(r.get("entry_type") or ""), str(r.get("entry_type") or "-")),
            "구분": _ASSET_SOURCE_LABELS.get(str(r.get("source_type") or ""), str(r.get("source_type") or "-")),
            "변동(분)": round(int(r.get("delta_seconds") or 0) / 60, 1),
            "잔액(분)": round(int(r.get("balance_after_seconds") or 0) / 60, 1),
            "사유": r.get("note") or "-",
        } for r in voice_ledger]
        st.dataframe(voice_rows, hide_index=True, use_container_width=True)
    else:
        st.caption("Voice 변동 기록이 없습니다.")


# ---------------------------------------------------------------------------
# Activity / Academy / AI pages with pagination
# ---------------------------------------------------------------------------
def _pager(prefix: str, page: int, has_next: bool) -> int:
    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("← 이전", key=f"{prefix}_prev", disabled=page <= 0, use_container_width=True):
        st.session_state[f"{prefix}_page"] = max(0, page - 1)
        st.rerun()
    if c2.button("다음 →", key=f"{prefix}_next", disabled=not has_next, use_container_width=True):
        st.session_state[f"{prefix}_page"] = page + 1
        st.rerun()
    c3.caption(f"{page + 1} 페이지")
    return page


def _render_activity(auth: HwarangAuthService, actor_id: str) -> None:
    """Legacy route compatibility: show only state-changing admin audit."""
    users=_fetch_users(auth); user_map={str(u.get("user_id")):u for u in users}; logs=auth.admin_audit_log(actor_id,limit=200)
    table=[{"시간":_fmt_dt(r.get("created_at")),"관리자":(user_map.get(str(r.get("actor_user_id"))) or {}).get("display_name") or r.get("actor_user_id"),"대상":(user_map.get(str(r.get("target_user_id"))) or {}).get("display_name") or r.get("target_user_id") or "-","작업":_ADMIN_ACTION_LABELS.get(str(r.get("action") or ""),str(r.get("action") or "-"))} for r in logs]
    st.dataframe(table,hide_index=True,use_container_width=True)


def _render_academy(auth: HwarangAuthService) -> None:
    operations = _operations_summary(auth)
    _statistics_status(operations, "hw_academy_refresh")
    counts = operations.get("academy", {}) if operations else {}
    users = _fetch_users(auth)
    user_map = {str(u.get("user_id")): u for u in users}
    sessions_recent = _cached_admin_read("academy:today_sessions",15,lambda:_safe_rows(auth,"/rest/v1/academy_sessions",params={"select":"id,user_id,status,interaction_mode,started_at,ended_at,updated_at","started_at":"gte."+_day_start_utc_iso(),"order":"started_at.desc","limit":"1000"})) if operations is None else []
    assessments_today = _cached_admin_read("academy:today_assessments",15,lambda:_safe_rows(auth,"/rest/v1/academy_assessments",params={"select":"id,user_id,overall_score,evaluator_type,generated_at","generated_at":"gte."+_day_start_utc_iso(),"order":"generated_at.desc","limit":"1000"})) if operations is None else []
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("오늘 시작", counts.get("today_started", len(sessions_recent)))
    c2.metric("오늘 완료", counts.get("today_completed", sum(1 for s in sessions_recent if s.get("status") == "completed")))
    c3.metric("오늘 정식 평가", counts.get("today_formal", sum(1 for r in assessments_today if r.get("evaluator_type") in ("ai", "hybrid"))))
    st.caption(f"오늘 규칙 기반 잠정 평가: {counts.get("today_rules", sum(1 for r in assessments_today if r.get("evaluator_type") == "rules"))}회 · 정식 평가와 별도 집계")
    c4.metric("Voice Session", counts.get("today_voice", sum(1 for s in sessions_recent if s.get("interaction_mode") == "VOICE")))

    tab = st.segmented_control(
        "ACADEMY 종류",
        ["sessions", "assessments"],
        default="sessions",
        format_func=lambda x: "Session" if x == "sessions" else "평가 결과",
        label_visibility="collapsed",
        key="hw_academy_tab_v2",
    )
    st.caption("사용자 성장 분석은 정식평가 데이터가 쌓인 뒤 같은 메뉴 안에서 확장할 수 있도록 구조를 유지합니다.")
    page_size = 100
    page_key = f"hw_academy_{tab}_page"
    page = int(st.session_state.get(page_key, 0))

    if tab == "sessions":
        rows = _safe_rows(
            auth,
            "/rest/v1/academy_sessions",
            params={
                "select": "id,user_id,status,stage,scenario_id,mode,training_focus,interaction_mode,last_turn_no,started_at,ended_at,updated_at,metadata",
                "order": "updated_at.desc",
                "limit": str(page_size),
                "offset": str(page * page_size),
            },
        )
        display = [{
            "사용자": (user_map.get(str(r.get("user_id"))) or {}).get("display_name") or r.get("user_id"),
            "상태": r.get("status"),
            "단계": r.get("stage"),
            "모드": r.get("mode"),
            "Focus": r.get("training_focus"),
            "방식": r.get("interaction_mode"),
            "Turn": r.get("last_turn_no") or 0,
            "시작": _fmt_dt(r.get("started_at")),
            "종료": _fmt_dt(r.get("ended_at")),
        } for r in rows]
    else:
        rows = _safe_rows(
            auth,
            "/rest/v1/academy_assessments",
            params={
                "select": "id,user_id,session_id,assessment_type,evaluator_type,overall_score,score_lower,score_upper,grade,status,generated_at",
                "order": "generated_at.desc",
                "limit": str(page_size),
                "offset": str(page * page_size),
            },
        )
        display = [{
            "사용자": (user_map.get(str(r.get("user_id"))) or {}).get("display_name") or r.get("user_id"),
            "평가": r.get("assessment_type"),
            "평가 방식": "규칙 기반 · 잠정" if r.get("evaluator_type") == "rules" else r.get("evaluator_type"),
            "점수": r.get("overall_score") if r.get("overall_score") is not None else f"{r.get("score_lower", "—")}–{r.get("score_upper", "—")}",
            "등급": r.get("grade") or "-",
            "상태": r.get("status") or "-",
            "생성": _fmt_dt(r.get("generated_at")),
        } for r in rows]
    if display:
        st.dataframe(display, hide_index=True, use_container_width=True)
    else:
        label = "상담 훈련" if tab == "sessions" else "평가 결과"
        st.info(f"이 페이지에 표시할 {label} 기록이 없습니다.")
    if display or page > 0:
        _pager(f"hw_academy_{tab}", page, len(rows) == page_size)


def _render_ai(auth: HwarangAuthService) -> None:
    operations = _operations_summary(auth)
    _statistics_status(operations, "hw_ai_refresh")
    st.caption("상담 훈련·평가·Voice의 학습 AI 사용 기록을 집계합니다.")
    users=_fetch_users(auth); user_map={str(u.get("user_id")):u for u in users}; policy=_fetch_credit_policy(auth)
    usage=_cached_admin_read("ai:usage_month",30,lambda:_safe_rows(auth,"/rest/v1/hwarang_admin_ai_usage_daily_view",params={
        "select":"usage_day,user_id,ai_role,model,request_count,input_tokens,cached_tokens,output_tokens,credits_charged,calculated_cost_usd",
        "usage_day":"gte."+_month_start_utc_iso(),"order":"usage_day.desc","limit":"1500"})) if operations is None else []
    voice_rows=_cached_admin_read("ai:voice_month",30,lambda:_safe_rows(auth,"/rest/v1/hwarang_ai_usage_log",params={
        "select":"user_id,voice_seconds_charged,created_at","created_at":"gte."+_month_start_utc_iso(),"voice_seconds_charged":"gt.0","limit":"1500"})) if operations is None else []
    failed=_cached_admin_read("ai:failed_month",30,lambda:_safe_rows(auth,"/rest/v1/hwarang_ai_request_registry",params={
        "select":"request_id,user_id,purpose,billing_bucket,status,actual_credits,actual_voice_seconds,block_reason,created_at",
        "created_at":"gte."+_month_start_utc_iso(),"or":"(status.in.(blocked,failed),block_reason.not.is.null)","order":"created_at.desc","limit":"500"}))
    today=[r for r in usage if _logged_in_today(r.get("usage_day"))]
    total_cost=sum(float(r.get("calculated_cost_usd") or 0) for r in usage); today_cost=sum(float(r.get("calculated_cost_usd") or 0) for r in today)
    voice_seconds=sum(int(r.get("voice_seconds_charged") or 0) for r in voice_rows); text_requests=sum(int(r.get("request_count") or 0) for r in usage if str(r.get("ai_role") or "")!="VOICE")
    if operations:
        totals = operations["ai"]
        total_cost, today_cost = float(totals["month_cost"]), float(totals["today_cost"])
        voice_seconds, text_requests = int(totals["voice_seconds"]), int(totals["text_requests"])
    failure_count = int(operations["ai"]["failed_count"]) if operations else len(failed)
    cols=st.columns(5); cols[0].metric("오늘 학습 AI 비용",f"${today_cost:,.2f}"); cols[1].metric("이번 달 학습 AI 비용",f"${total_cost:,.2f}"); cols[2].metric("Text/평가 요청",f"{text_requests:,}"); cols[3].metric("Voice 사용",f"{voice_seconds/60:.1f}분"); cols[4].metric("차단/실패",failure_count)
    budget=float(policy.get("monthly_ai_budget_usd") or 0); warn=int(policy.get("budget_warning_percent") or 80)
    if budget>0:
        ratio=total_cost/budget*100; st.markdown("##### 월 학습 AI 운영 예산"); st.progress(min(1.0,max(0.0,ratio/100))); st.caption(f"USD {total_cost:,.2f} / USD {budget:,.2f} · {ratio:.1f}% 사용 · {warn}%부터 관리자 경고")
    by_user={}; by_model={}
    for row in usage:
        uid=str(row.get("user_id") or ""); req=int(row.get("request_count") or 0); slot=by_user.setdefault(uid,{"requests":0,"credits":0,"voice_seconds":0,"cost":0.0}); slot["requests"]+=req; slot["credits"]+=int(row.get("credits_charged") or 0); slot["cost"]+=float(row.get("calculated_cost_usd") or 0)
        model=str(row.get("model") or "-"); m=by_model.setdefault(model,{"requests":0,"cost":0.0}); m["requests"]+=req; m["cost"]+=float(row.get("calculated_cost_usd") or 0)
    for row in voice_rows:
        uid=str(row.get("user_id") or ""); by_user.setdefault(uid,{"requests":0,"credits":0,"voice_seconds":0,"cost":0.0})["voice_seconds"]+=int(row.get("voice_seconds_charged") or 0)
    if operations:
        by_user = {str(r["user_id"]): {"requests":int(r["requests"]),"credits":int(r["credits"]),"voice_seconds":int(r["voice_seconds"]),"cost":float(r["cost"])} for r in operations.get("by_user", [])}
        by_model = {str(r["model"]): {"requests":int(r["requests"]),"cost":float(r["cost"])} for r in operations.get("by_model", [])}
    left,right=st.columns(2,gap="large")
    with left:
        st.markdown("##### 사용자별"); rows=[{"사용자":(user_map.get(uid) or {}).get("display_name") or uid,"호출":v["requests"],"훈련 크레딧":v["credits"],"Voice(분)":round(v["voice_seconds"]/60,2),"예상비용(USD)":round(v["cost"],6)} for uid,v in sorted(by_user.items(),key=lambda x:x[1]["cost"],reverse=True)]; st.dataframe(rows,hide_index=True,use_container_width=True) if rows else st.caption("아직 실제 AI 호출 기록이 없습니다.")
    with right:
        st.markdown("##### 모델별"); rows=[{"모델":m,"호출":v["requests"],"예상비용(USD)":round(v["cost"],6)} for m,v in sorted(by_model.items(),key=lambda x:x[1]["cost"],reverse=True)]; st.dataframe(rows,hide_index=True,use_container_width=True) if rows else st.caption("모델 사용 기록이 없습니다.")
    st.caption("실패·차단 목록은 최근 200건을 표시하며, 위 총계는 전체 기록을 집계합니다." if operations else "실패·차단 목록은 조회된 기록 기준입니다.")
    st.markdown("##### 실패 · 차단"); blocked=[{"시간":_fmt_dt(r.get("created_at")),"사용자":(user_map.get(str(r.get("user_id"))) or {}).get("display_name") or r.get("user_id"),"용도":r.get("purpose"),"상태":r.get("status"),"사유":r.get("block_reason") or "-"} for r in failed[:200]]; st.dataframe(blocked,hide_index=True,use_container_width=True) if blocked else st.caption("이번 달 차단/실패 기록이 없습니다.")
    with st.expander("상세 원장"):
        st.caption("상세 원장은 필요할 때만 불러옵니다.")
        if st.checkbox("상세 원장 불러오기",key="hw_admin_ai_load_detail"):
            details=_safe_rows(auth,"/rest/v1/hwarang_ai_usage_log",params={"select":"user_id,ai_role,model,input_tokens,cached_tokens,output_tokens,credits_charged,voice_seconds_charged,calculated_cost_usd,status,created_at","created_at":"gte."+_month_start_utc_iso(),"order":"created_at.desc","limit":"500"})
            for r in details: r["사용자"]=(user_map.get(str(r.get("user_id"))) or {}).get("display_name") or r.get("user_id")
            st.dataframe(details,hide_index=True,use_container_width=True)


# ---------------------------------------------------------------------------
# System settings
# ---------------------------------------------------------------------------
def _render_pre_api_self_test() -> None:
    if st.button("PRE-API 자가진단 실행", type="secondary", use_container_width=True, key="hw_pre_api_self_test_v2"):
        try:
            from hwarang_academy.pre_api.case_engine import create_case
            from hwarang_academy.pre_api.mock_ai import MockAIAdapter
            from hwarang_academy.pre_api.readiness import pre_api_readiness
            from hwarang_academy.pre_api.runtime import PreAPIRuntime

            case = create_case(20261004, training_mode="SOLO", training_focus="comprehensive")
            engine = PreAPIRuntime(MockAIAdapter())
            turn = engine.customer_turn(
                case=case,
                advisor_text="현재 보험을 점검받고 싶으신 가장 큰 이유가 무엇인가요?",
                transcript=[],
                session_state={},
                turn_no=1,
            )
            coach = engine.coach(
                case=case,
                advisor_text="현재 보험을 점검받고 싶으신 가장 큰 이유가 무엇인가요?",
                transcript=[],
                session_state=turn.session_state,
            )
            evaluator = engine.evaluate(
                case=case,
                transcript=[
                    {"role": "advisor", "turn": 1, "text": "현재 보험을 점검받고 싶으신 가장 큰 이유가 무엇인가요?"},
                    {"role": "customer", "turn": 1, "text": turn.customer_text},
                ],
                evidence_log=[turn.evidence],
            )
            voice = engine.voice_session_spec(case=case, stage="M1")
            directive = engine.voice_directive(turn)
            structural = pre_api_readiness()
            checks = {
                "Customer 구조화 응답": bool(turn.customer_text),
                "Python 상태 검증": bool(turn.validated_payload),
                "Coach 구조화 응답": bool(coach.payload.get("improve_next")),
                "Evaluator 18개 역량": len(evaluator.payload.get("competencies") or []) == 18,
                "평가 Snapshot Hash": len(evaluator.source_snapshot_hash) == 64,
                "Voice GPT-Live-1": voice.get("provider_model") == "gpt-live-1",
                "Voice Directive": directive.get("contract_version") is not None,
                "PRE-API 구조 준비": bool(structural.get("pre_api_ready")),
            }
            if all(checks.values()):
                st.success("PRE-API 자가진단을 통과했습니다. 외부 AI 호출은 발생하지 않았습니다.")
            else:
                st.warning("일부 PRE-API 자가진단 항목을 확인해야 합니다.")
            st.dataframe(
                [{"점검 항목": k, "결과": "PASS" if v else "CHECK"} for k, v in checks.items()],
                hide_index=True,
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"PRE-API 자가진단 실패: {exc}")


def _render_settings(auth: HwarangAuthService, actor_id: str) -> None:
    runtime = _fetch_runtime(auth)
    policy = _fetch_credit_policy(auth)
    if not runtime:
        st.warning("먼저 Supabase Migration 09~13을 적용해 주세요.")
        return

    st.markdown('<div class="hw-section-head">AI 서비스</div>', unsafe_allow_html=True)
    with st.form("hw_ai_runtime_settings_v2"):
        service_enabled = st.toggle("AI 서비스", value=bool(runtime.get("service_enabled")))
        c1, c2, c3 = st.columns(3)
        text_enabled = c1.toggle("Text AI", value=bool(runtime.get("text_enabled")))
        voice_enabled = c2.toggle("Voice AI", value=bool(runtime.get("voice_enabled")))
        assessment_enabled = c3.toggle("AI 정식평가", value=bool(runtime.get("assessment_enabled")))
        contact_label = st.text_input(
            "이용량 추가 문의 문구",
            value=str(runtime.get("contact_label") or "박병선 팀장에게 이용량 추가 문의"),
        )
        contact_url = st.text_input("문의 링크", value=str(runtime.get("contact_url") or ""))
        saved = st.form_submit_button("AI 서비스 설정 저장", type="primary", use_container_width=True)
    if saved:
        _safe_rpc(
            auth,
            "admin_update_hwarang_ai_runtime",
            {
                "p_actor_user_id": actor_id,
                "p_service_enabled": service_enabled,
                "p_text_enabled": text_enabled,
                "p_voice_enabled": voice_enabled,
                "p_assessment_enabled": assessment_enabled,
                "p_soft_limit_percent": max(1, min(99, 100 - int(policy.get("remaining_warning_percent") or 20))),
                "p_contact_label": contact_label,
                "p_contact_url": contact_url,
            },
        )
        st.success("AI 서비스 설정을 저장했습니다.")
        st.rerun()

    st.markdown('<div class="hw-section-head">크레딧 · 예산 정책</div>', unsafe_allow_html=True)
    with st.form("hw_credit_policy_v2"):
        c1, c2, c3 = st.columns(3)
        monthly_free = c1.number_input(
            "월 기본 훈련 크레딧",
            min_value=0,
            value=int(policy.get("monthly_free_credits") or 1000),
            step=100,
        )
        remaining_warning = c2.slider(
            "잔여 이용량 경고 기준",
            min_value=1,
            max_value=99,
            value=int(policy.get("remaining_warning_percent") or 20),
            step=1,
            help="실제 사용 가능한 총 훈련 크레딧이 이 기준 이하 구간에 들어오면 경고합니다.",
        )
        default_voice = c3.number_input(
            "신규 사용자 Voice 기본량(분)",
            min_value=0,
            value=int(policy.get("default_voice_minutes") or 0),
            step=10,
        )
        b1, b2 = st.columns(2)
        monthly_budget = b1.number_input(
            "월 AI 운영 예산(USD)",
            min_value=0.0,
            value=float(policy.get("monthly_ai_budget_usd") or 50),
            step=10.0,
        )
        budget_warning = b2.slider(
            "월 예산 경고 기준",
            min_value=1,
            max_value=99,
            value=int(policy.get("budget_warning_percent") or 80),
            step=1,
        )
        st.markdown(
            f"""
            <div class="hw-policy-note">
              월 기본 크레딧은 매월 1일 KST 기준으로 <b>{int(monthly_free):,}</b>으로 복원되며 미사용분은 누적되지 않습니다.<br>
              구매/추가 크레딧은 만료되지 않고 계속 이월되며 <b>월 기본 → 구매/추가</b> 순서로 사용됩니다.<br>
              잔여 이용량이 기본 제공량 기준 <b>{int(remaining_warning)}%</b> 이하 구간에 들어오면 사용자에게 경고합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        policy_saved = st.form_submit_button("크레딧 · 예산 정책 저장", type="primary", use_container_width=True)
    if policy_saved:
        _safe_rpc(
            auth,
            "admin_update_hwarang_credit_policy",
            {
                "p_actor_user_id": actor_id,
                "p_monthly_free_credits": int(monthly_free),
                "p_remaining_warning_percent": int(remaining_warning),
                "p_default_voice_minutes": int(default_voice),
                "p_monthly_ai_budget_usd": float(monthly_budget),
                "p_budget_warning_percent": int(budget_warning),
            },
        )
        st.success("크레딧·예산 정책을 저장했습니다. 월 기본량 변경은 기존 사용자의 다음 월 갱신부터 적용됩니다.")
        st.rerun()

    st.markdown('<div class="hw-section-head">AI 모델</div>', unsafe_allow_html=True)
    policies = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_model_policy",
        params={
            "select": "role_code,display_name,provider_model,billing_bucket,max_output_tokens,is_active,policy_version,updated_at",
            "order": "role_code.asc",
        },
    )
    if policies:
        display = [{
            "역할": r.get("display_name"),
            "모델": r.get("provider_model") or "API 연결 시 확정",
            "이용량": "Voice 이용량" if r.get("billing_bucket") == "VOICE" else "훈련 크레딧",
            "최대 출력": r.get("max_output_tokens") or "-",
            "정책 버전": r.get("policy_version"),
        } for r in policies]
        st.dataframe(display, hide_index=True, use_container_width=True)
        st.caption("Voice V1은 GPT-Live-1입니다. Customer / Coach / Evaluator 모델 ID는 실제 API 연결 시점에 최종 확정합니다.")

    st.markdown('<div class="hw-section-head">Guardrail</div>', unsafe_allow_html=True)
    limits = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_limit_policies",
        params={
            "select": "scope_key,metric,soft_limit,hard_limit,is_enabled,metadata",
            "scope_type": "eq.app",
            "order": "scope_key.asc,metric.asc",
        },
    )
    if limits:
        st.dataframe(limits, hide_index=True, use_container_width=True)
    st.caption("정상 이용에는 분당 호출 제한을 두지 않고 중복 요청·동시 Session·입출력 크기·Voice 장시간 방치만 방어합니다.")

    st.markdown('<div class="hw-section-head">시스템 진단</div>', unsafe_allow_html=True)
    _render_pre_api_self_test()

    st.markdown('<div class="hw-section-head">위험 영역</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hw-danger"><strong>AI 서비스 긴급 정지</strong><p>모든 외부 AI 호출만 즉시 중단합니다. WORKSPACE, CALCULATOR와 비-AI ACADEMY 기능은 계속 이용할 수 있습니다.</p></div>
        """,
        unsafe_allow_html=True,
    )
    confirm_key = "hw_confirm_ai_kill_v2"
    if not runtime.get("service_enabled"):
        st.info("현재 AI 서비스는 정지 상태입니다.")
    elif st.session_state.get(confirm_key):
        st.warning("정말 AI 서비스를 긴급 정지하시겠습니까?")
        c1, c2 = st.columns(2)
        if c1.button("취소", key="hw_cancel_ai_kill_v2", use_container_width=True):
            st.session_state[confirm_key] = False
            st.rerun()
        if c2.button("AI 서비스 긴급 정지 확인", key="hw_apply_ai_kill_v2", type="primary", use_container_width=True):
            _safe_rpc(
                auth,
                "admin_update_hwarang_ai_runtime",
                {
                    "p_actor_user_id": actor_id,
                    "p_service_enabled": False,
                    "p_text_enabled": bool(runtime.get("text_enabled")),
                    "p_voice_enabled": bool(runtime.get("voice_enabled")),
                    "p_assessment_enabled": bool(runtime.get("assessment_enabled")),
                    "p_soft_limit_percent": int(runtime.get("soft_limit_percent") or 80),
                    "p_contact_label": str(runtime.get("contact_label") or ""),
                    "p_contact_url": str(runtime.get("contact_url") or ""),
                },
            )
            st.session_state[confirm_key] = False
            st.warning("AI 서비스를 정지했습니다.")
            st.rerun()
    else:
        if st.button("AI 서비스 긴급 정지", key="hw_start_ai_kill_v2", use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render(auth: HwarangAuthService) -> None:
    _inject_css()
    try:
        actor_id, _viewer = _require_actor(auth)
    except HwarangAuthError as exc:
        st.error(str(exc))
        return

    page = str(st.session_state.setdefault("hw_admin_center_page", "dashboard"))
    if page not in _PAGE_LABELS:
        page = "dashboard"
        st.session_state["hw_admin_center_page"] = page

    _top_header(page)
    try:
        if page == "dashboard":
            _render_dashboard(auth, actor_id)
        elif page == "accounts":
            _render_accounts(auth, actor_id)
        elif page == "academy":
            _render_academy(auth)
        elif page == "ai":
            _render_ai(auth)
        else:
            _render_settings(auth, actor_id)
    except HwarangAuthError as exc:
        st.error(str(exc))
