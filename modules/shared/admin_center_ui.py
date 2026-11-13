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
from modules.shared.refresh import refresh_current

from modules.shared.ai_guardrails import (
    credit_display_state,
    get_training_credit_status,
    training_credit_display_state,
    voice_display_state,
)
from modules.shared.external_apps import academy_url, calculator_url
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService
from modules.shared import admin_assets


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
    "operations": "운영 점검",
    "accounts": "계정 · 권한",
    "academy": "ACADEMY 관리",
    "ai": "AI 사용량 · 비용",
    "settings": "시스템 설정",
}
_PAGE_SUBTITLES = {
    "dashboard": "플랫폼 운영 상태와 지금 확인해야 할 항목을 한눈에 봅니다.",
    "operations": "문제와 근거를 확인하고 점검 기록·요청문을 정리합니다.",
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
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise HwarangAuthError("조회 결과를 확인하지 못했습니다. 다시 조회해 주세요.")
    return rows


def _safe_rpc(auth: HwarangAuthService, path: str, payload: dict[str, Any]) -> Any:
    if path in admin_assets.RPC_NAMES:
        try:
            return admin_assets.apply(auth, st.session_state, path, payload)
        finally:
            # An uncertain write may already have committed. Never reuse old balances.
            _clear_admin_read_cache()
            st.session_state.pop("hw_admin_reference_cache", None)
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


def _fetch_users(auth: HwarangAuthService) -> list[dict[str, Any]]:
    rows = _cached_admin_read("reference:users", 15, l…19905 tokens truncated…iv class="hw-section-head">Guardrail</div>', unsafe_allow_html=True)
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
            refresh_current()
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
            refresh_current()
    else:
        if st.button("AI 서비스 긴급 정지", key="hw_start_ai_kill_v2", use_container_width=True):
            st.session_state[confirm_key] = True
            refresh_current()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _render_asset_recovery(auth):
    pending = st.session_state.get(admin_assets.PENDING)
    if pending:
        st.warning('결과 확인이 필요한 자산 처리가 있습니다. 확인 전에는 새로운 자산 처리를 실행할 수 없습니다.')
        st.caption(f"대상 {len(pending['p_target_user_ids'])}명 · "
                   f"{_ASSET_TYPE_LABELS[pending['p_asset']]} · "
                   f"{_ASSET_OPERATION_LABELS[pending['p_operation']]} · 1인당 {pending['p_amount']:,}")
        left, right = st.columns(2)
        check = left.button('처리 결과 확인', key='hw_asset_check')
        retry = right.button('같은 요청 안전하게 재시도', key='hw_asset_retry')
        if check or retry:
            try:
                result = admin_assets.resolve(auth,st.session_state,send=retry)
                if result is None:
                    st.info('아직 확인된 결과가 없습니다. 진행 중일 수 있으므로 잠시 후 확인하거나 같은 요청을 재시도해 주세요.')
                else:
                    st.session_state.pop('hw_admin_bulk_asset_pending_v4',None)
                    st.session_state.pop('hw_admin_bulk_asset_retry_v4',None)
                    _clear_admin_read_cache()
                    refresh_current()
            except HwarangAuthError as exc:
                st.error(str(exc))
    receipt = st.session_state.get(admin_assets.RESULT)
    if receipt:
        result, request = receipt['result'], receipt['request']
        st.info(f"최근 자산 처리 · 성공 {result['success_count']}명 / 실패 {result['failed_count']}명")
        failures = [row for row in result['results'] if row['status']=='failed']
        if failures:
            try:
                names = {str(u['user_id']):str(u.get('display_name') or u.get('login_id') or '대상 계정') for u in _fetch_users(auth)}
            except HwarangAuthError:
                names = {}
            st.dataframe([{'대상 계정':names.get(r['user_id'],'대상 계정'),'실패 사유':admin_assets.failure_message(r.get('error'))}
                          for r in failures],hide_index=True,use_container_width=True)
            if st.button('실패 대상만 다시 검토', key='hw_asset_failed_review'):
                st.session_state['hw_admin_bulk_asset_pending_v4'] = dict(
                    user_ids=[r['user_id'] for r in failures],user_names=[names.get(r['user_id'],'대상 계정') for r in failures],
                    asset_type=request['p_asset'],operation=request['p_operation'],
                    source_type=request['p_source_type'],amount=request['p_amount'],note=request['p_note'])
                st.session_state.pop('hw_admin_selected_user_id',None)
                st.session_state['hw_admin_center_page']='accounts'
                refresh_current()


@st.fragment
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

    from modules.shell.page_slot import page_slot
    with page_slot('admin:'+page):
        _top_header(page)
        if page != "operations":
            _render_asset_recovery(auth)
        try:
            if page == "dashboard":
                _render_dashboard(auth, actor_id)
            elif page == "operations":
                from modules.shared.operations_ui import render as render_operations
                render_operations(auth, actor_id)
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
