"""Administration of the retiring consultation simulator, Credit and Voice."""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from . import admin_assets
from .admin_center_ui import (
    _APP_LABELS, _KST, _account_filters, _cached_admin_read, _chip, _clear_admin_read_cache,
    _day_start_utc_iso, _fmt_dt, _fmt_relative, _last_24h_utc_iso, _logged_in_today,
    _metric_card, _month_start_utc_iso, _page_change, _require_actor, _safe_rows,
)
from .ai_guardrails import get_training_credit_status, training_credit_display_state, voice_display_state
from .external_apps import academy_url, calculator_url
from .hwarang_auth import HwarangAuthError, HwarangAuthService
from .refresh import refresh_current
from .operations import display_time, now, require

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

    studio_ops = None
    try:
        from hwarang_academy.studio.repository import Repository
        studio_ops = Repository(auth, actor_id).rpc('operations') or {}
    except Exception:
        st.warning('AI 상담 보류·비용 상태를 확인하지 못했습니다. SQL 25 적용과 운영 권한을 확인해 주세요.')
    unknown_count = sum(int((studio_ops or {}).get(k) or 0) for k in ('unknown_cost','recovered_unknown','pending'))
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
        _metric_card("오늘 기록된 학습 AI 비용", f"${today_cost:,.2f}", "미확인 비용 별도 · 총액 확정 불가" if unknown_count or studio_ops is None else "현재 사용 원장에 기록된 금액")

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
            ("high", "AI 상담 처리 보류", int((studio_ops or {}).get('pending') or 0), "건 · 학습 AI에서 복구", "ai"),
            ("high", "AI 상담 실패", int((studio_ops or {}).get('failed_24h') or 0), "건 / 최근 24시간", "ai"),
            ("medium", "비용 미확인 기록", unknown_count, "건 · 중복 포함 가능", "ai"),
            ("high", "AI 요청 실패·차단", len(failed), "최근 24시간", "ai"),
            ("medium", f"훈련 크레딧 잔여 {remaining_warning}% 이하", len(low_training), "사용자", "assets"),
            ("medium", f"Voice 잔여 {remaining_warning}% 이하", len(low_voice), "사용자", "assets"),
            ("medium", "24시간 이상 미종료 Session", len(stale), "Session", "academy"),
            ("low", "비활성 계정", len(inactive), "계정", "assets"),
        ]
        visible = [x for x in alerts if x[2] > 0]
        if not visible and studio_ops is not None:
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
            st.caption(f"기록된 비용 USD {month_cost:,.2f} / 예산 USD {budget:,.2f} · 확인된 비율 {ratio:.1f}%")
            if unknown_count or studio_ops is None:
                st.warning("미확인 비용이 있어 실제 예산 사용률은 확정할 수 없습니다.")
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


def _render_accounts(auth: HwarangAuthService, actor_id: str) -> None:
    users = _fetch_users(auth)
    selected_id = st.session_state.get("hw_admin_asset_user_id")
    if selected_id:
        selected = next((u for u in users if str(u.get("user_id")) == str(selected_id)), None)
        if selected:
            st.button("← 자산 목록", on_click=st.session_state.pop, args=("hw_admin_asset_user_id", None))
            uid = str(selected["user_id"])
            tab = st.radio("상담 운영", ["개요", "상담 이력", "자산 조정"], horizontal=True)
            if tab == "개요":
                _user_overview(auth, uid, selected)
            elif tab == "상담 이력":
                _user_academy(auth, uid)
            else:
                _user_ai(auth, actor_id, uid)
            return
        st.session_state.pop("hw_admin_asset_user_id", None)

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
        key="hw_admin_asset_user_table",
    )
    try:
        selected_rows = [int(i) for i in event.selection.rows]
    except Exception:
        selected_rows = []
    selected_users = [filtered[i] for i in selected_rows if 0 <= i < len(filtered)]

    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    with c1:
        if len(selected_users) == 1 and st.button("선택 계정 상세", type="primary", use_container_width=True):
            st.session_state["hw_admin_asset_user_id"] = str(selected_users[0]["user_id"])
            refresh_current()
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
            refresh_current()
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
            result = admin_assets.validate_result(result, pending['user_ids'])
            success_count = result['success_count']
            failed_count = result['failed_count']
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
                            "실패 사유": admin_assets.failure_message(row.get("error")),
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
            refresh_current()


def _user_overview(auth: HwarangAuthService, uid: str, user: dict[str, Any]) -> None:
    since=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
    sessions=_safe_rows(auth,"/rest/v1/academy_sessions",params={"select":"id,status,mode,stage,interaction_mode,started_at,ended_at","user_id":f"eq.{uid}","started_at":"gte."+since,"order":"started_at.desc","limit":"200"})
    credit=get_training_credit_status(auth,uid)
    cols=st.columns(4); cols[0].metric("최근 로그인",_fmt_relative(user.get("last_login_at"))); cols[1].metric("ACADEMY Session",len(sessions)); cols[2].metric("완료 Session",sum(1 for row in sessions if row.get("status")=="completed")); cols[3].metric("훈련 크레딧",f"{credit.available_credits:,}" if credit else "-")
    if credit:
        st.markdown('<div class="hw-section-head">크레딧 구성</div>',unsafe_allow_html=True); c1,c2,c3=st.columns(3); c1.metric("이번 달 기본",f"{credit.monthly_available_credits:,}"); c2.metric("구매/추가",f"{credit.purchased_available_credits:,}"); c3.metric("Voice",f"{credit.voice_available_seconds/60:.0f}분"); st.caption("월 기본 크레딧이 먼저 사용되며 구매/추가 크레딧은 만료되지 않습니다.")


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
    display = [{"상태": "완료" if r.get("status") in ("completed","stopped") else "미완료", "모드": "자유 연습"}
               if r.get("mode") != "ASSESSMENT" else row for r,row in zip(sessions,display) if r.get("mode")=="ASSESSMENT" or int(r.get("last_turn_no") or 0)>0]
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
                refresh_current()

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
                refresh_current()

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


def _pager(prefix: str, page: int, has_next: bool) -> int:
    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("← 이전", key=f"{prefix}_prev", disabled=page <= 0, use_container_width=True):
        st.session_state[f"{prefix}_page"] = max(0, page - 1)
        refresh_current()
    if c2.button("다음 →", key=f"{prefix}_next", disabled=not has_next, use_container_width=True):
        st.session_state[f"{prefix}_page"] = page + 1
        refresh_current()
    c3.caption(f"{page + 1} 페이지")
    return page


def _render_academy(auth: HwarangAuthService) -> None:
    with st.expander("AI 상담 Studio · 참여 현황 / 공유 / 공식 평가"):
        from hwarang_academy.studio.ui import render_manager
        actor_id, _ = _require_actor(auth)
        render_manager(auth, actor_id)
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
                "select": "id,user_id,session_id,assessment_type,evaluator_type,overall_score,score_lower,score_upper,grade,status,generated_at,academy_sessions!inner(mode)",
                "academy_sessions.mode": "eq.ASSESSMENT",
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
    if tab == "sessions":
        display = [{"사용자": row["사용자"], "모드": "자유 연습", "완료 여부": "완료" if r.get("status") in ("completed","stopped") else "미완료"}
                   if r.get("mode") != "ASSESSMENT" else row for r,row in zip(rows,display) if r.get("mode")=="ASSESSMENT" or int(r.get("last_turn_no") or 0)>0]
    if display:
        st.dataframe(display, hide_index=True, use_container_width=True)
    else:
        label = "상담 훈련" if tab == "sessions" else "평가 결과"
        st.info(f"이 페이지에 표시할 {label} 기록이 없습니다.")
    if display or page > 0:
        _pager(f"hw_academy_{tab}", page, len(rows) == page_size)


def _render_ai(auth: HwarangAuthService) -> None:
    from hwarang_academy.studio.ui import render_operations
    actor_id, _ = _require_actor(auth)
    render_operations(auth, actor_id)
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
    cols=st.columns(5); cols[0].metric("오늘 확인된 학습 AI 비용",f"${today_cost:,.2f}"); cols[1].metric("이번 달 확인된 학습 AI 비용",f"${total_cost:,.2f}"); cols[2].metric("Text/평가 요청",f"{text_requests:,}"); cols[3].metric("Voice 사용",f"{voice_seconds/60:.1f}분"); cols[4].metric("차단/실패",failure_count)
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
        by_user = {str(r["user_id"]): {"requests":int(r["requests"]),"credits":int(r["credits"]),"voice_seconds":int(r["voice_seconds"]),"cost":float(r["cost"] or 0)} for r in operations.get("by_user", [])}
        by_model = {str(r["model"]): {"requests":int(r["requests"]),"cost":float(r["cost"] or 0)} for r in operations.get("by_model", [])}
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


def _render_pre_api_self_test() -> None:
    if st.button("구조 자가진단 실행 · 외부 AI 미호출", type="secondary", use_container_width=True, key="hw_pre_api_self_test_v2"):
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
        service_enabled = st.toggle("전체 AI 서비스 · 학습과 브리핑", value=bool(runtime.get("service_enabled")))
        st.caption('끄면 학습 AI와 새 브리핑 생성을 모두 중단합니다. 저장된 자료 조회·공유·PDF는 계속 사용할 수 있습니다.')
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
        refresh_current()

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
        refresh_current()

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
            "모델": r.get("provider_model") or "기존 정책 미지정",
            "이용량": "Voice 이용량" if r.get("billing_bucket") == "VOICE" else "훈련 크레딧",
            "최대 출력": r.get("max_output_tokens") or "-",
            "정책 버전": r.get("policy_version"),
        } for r in policies]
        st.dataframe(display, hide_index=True, use_container_width=True)
        st.caption("위 표는 기존 학습 엔진 정책입니다. 현재 AI 상담의 실제 모델은 학습 AI → AI 상담 모델·차감 설정에서 확인합니다.")

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
                st.session_state.pop('hw_admin_asset_user_id',None)
                st.session_state['hw_admin_center_page']='accounts'
                refresh_current()


def studio_report_overview(auth, actor):
    require(auth, actor)
    incidents = auth._request('POST', '/rest/v1/rpc/hwarang_studio_report_incidents',
                              admin=True, json={'p_actor': actor})
    return {'collected_at': now(), 'incidents': incidents or []}


def studio_report_issues(data):
    reasons = {
        'duplicate_criterion': '평가 항목 중복',
        'criterion_set_mismatch': '평가 항목 구성 불일치',
        'invalid_evidence_turn': '근거 회차 불일치',
        'evidence_quote_mismatch': '학습자 원문과 인용 불일치',
        'missing_evidence': '평가 근거 누락',
    }
    issues = []
    for row in data['incidents']:
        session = str(row['session_id'])
        reason = reasons.get(row['reason'], '미분류')
        mode = '공식 평가' if row['purpose'] == 'EVALUATOR' else '연습 피드백'
        credit = '정산 미확인'
        charged = row.get('credits_charged')
        if charged is not None:
            if row['credit_status'] == 'failed' and charged == 0:
                credit = '예약 해제 · 0 Credit'
            elif row['credit_status'] == 'expired' and charged == 0:
                credit = '예약 만료 · 0 Credit'
            elif row['credit_status'] == 'completed':
                credit = f'{charged} Credit 차감'
        cost = '원장 기록 확인' if row.get('cost_status') == 'known' else '금액 미확인'
        issues.append({
            'id': 'studio-report:' + session, 'evidence': row['recorded_at'],
            'title': mode + ' 근거 검증 실패 · ' + session[:8],
            'area': 'ACADEMY / 상담 Studio / ' + mode,
            'result': '실패', 'impact': '사용 가능한 피드백이 생성되지 않음',
            'change': '운영 기록', 'classification': '평가 결과 검증 실패',
            'fact': f'세션 {session[:8]} · {display_time(row["recorded_at"])} · {reason} · 학습자 정산 {credit} · 공급자 비용 {cost}',
            'cause': reason, 'error': reason,
            'source': '관리자센터 상담 이력 · 평가의 상담 평가 진단',
            'reproduction': '같은 실패 사유를 넣은 모의 평가 응답으로 검증한다.',
            'expected': '실패를 기록하고 예약을 해제하며, 공급자 사용 기록을 보존한다.',
            'minimum': '결과 구조와 근거 검증을 대조하여 원인을 확인한다.',
            'next': '실패 사유와 Credit 원장 상태를 대조한다.',
            'first': row['recorded_at'], 'last': row['recorded_at'],
        })
    return issues


def render(page, auth, actor_id):
    _render_asset_recovery(auth)
    if page == "assets":
        _render_accounts(auth, actor_id)
    elif page == "simulator_dashboard":
        _render_dashboard(auth, actor_id)
    elif page == "academy":
        _render_academy(auth)
        incidents = studio_report_issues(studio_report_overview(auth, actor_id))
        st.subheader("상담 평가 진단")
        if incidents:
            st.dataframe([{"현상": issue["title"], "근거": issue["fact"]} for issue in incidents],
                         hide_index=True, use_container_width=True)
        else:
            st.caption("최근 7일간 확인된 평가 진단 기록이 없습니다.")
    elif page == "ai":
        _render_ai(auth)
    elif page == "settings":
        _render_settings(auth, actor_id)
