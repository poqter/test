"""HWARANG super-admin operations center.

This is the single super-admin console for accounts, activity, ACADEMY,
AI usage/credits and runtime settings. It intentionally keeps normal admin
roles from inheriting super-admin capabilities.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from modules.shared.ai_guardrails import credit_display_state, get_training_credit_status
from modules.shared.hwarang_auth import HwarangAuthError, HwarangAuthService


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
    "accounts": "계정 · 권한",
    "activity": "활동 기록",
    "academy": "ACADEMY 관리",
    "ai": "AI 사용량 · 비용",
    "settings": "시스템 설정",
}


def _require_actor(auth: HwarangAuthService) -> tuple[str, dict[str, Any]]:
    viewer = st.session_state.get("login_profile") or {}
    actor_id = str(viewer.get("id") or "")
    if viewer.get("role") != "super_admin" or not actor_id:
        raise HwarangAuthError("관리자 센터는 최고관리자만 이용할 수 있습니다.")
    auth._require_super_admin(actor_id)
    return actor_id, viewer


def _safe_rows(auth: HwarangAuthService, path: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = auth._request("GET", path, admin=True, params=params)
    return rows if isinstance(rows, list) else []


def _fmt_dt(value: Any) -> str:
    if not value:
        return "-"
    raw = str(value)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw[:16].replace("T", " ")


def _active_recent(value: Any, minutes: int = 10) -> bool:
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt.astimezone(timezone.utc)).total_seconds() <= minutes * 60
    except Exception:
        return False


def _fetch_users(auth: HwarangAuthService, actor_id: str) -> list[dict[str, Any]]:
    auth._require_super_admin(actor_id)
    try:
        rows = _safe_rows(
            auth,
            "/rest/v1/hwarang_admin_user_operations_view",
            params={"select": "*", "order": "display_name.asc.nullslast,login_id.asc"},
        )
        if rows:
            return rows
    except HwarangAuthError:
        pass
    return auth.admin_list_users(actor_id)


def _fetch_runtime(auth: HwarangAuthService) -> dict[str, Any]:
    rows = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_runtime_config",
        params={"select": "*", "config_id": "eq.1", "limit": "1"},
    )
    return rows[0] if rows else {}


def _top_header() -> None:
    st.markdown(
        """
        <div style="padding:4px 0 10px">
          <div style="font-size:12px;font-weight:800;letter-spacing:.08em;color:#71859b">HWARANG PLATFORM</div>
          <div style="font-size:30px;font-weight:900;letter-spacing:-.04em;color:#16334f">관리자 센터</div>
          <div style="margin-top:4px;color:#718096;font-size:14px">계정·활동·ACADEMY·AI 운영을 한 곳에서 관리합니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _nav() -> str:
    current = st.session_state.setdefault("hw_admin_center_page", "dashboard")
    selected = st.segmented_control(
        "관리자 메뉴",
        options=list(_PAGE_LABELS),
        default=current,
        format_func=lambda x: _PAGE_LABELS[x],
        key="hw_admin_center_nav",
        label_visibility="collapsed",
    )
    page = selected or current
    st.session_state["hw_admin_center_page"] = page
    return page


def _metric_row(users: list[dict[str, Any]], activity: list[dict[str, Any]], sessions: list[dict[str, Any]], ai_today: list[dict[str, Any]]) -> None:
    active_users = sum(1 for u in users if _active_recent(u.get("recent_seen_at")))
    ai_sessions = sum(1 for s in sessions if str(s.get("status") or "") == "in_progress")
    cost = sum(float(r.get("calculated_cost_usd") or 0) for r in ai_today)
    cols = st.columns(4)
    cols[0].metric("전체 사용자", len(users))
    cols[1].metric("최근 활동 사용자", active_users)
    cols[2].metric("진행 중 ACADEMY", ai_sessions)
    cols[3].metric("오늘 AI 예상비용", f"${cost:,.4f}")


def _render_dashboard(auth: HwarangAuthService, actor_id: str, users: list[dict[str, Any]]) -> None:
    st.subheader("운영 현황")
    activity = _safe_rows(
        auth,
        "/rest/v1/hwarang_activity_log",
        params={"select": "id,user_id,app_code,event_code,feature_code,outcome,created_at", "order": "created_at.desc", "limit": "100"},
    )
    sessions = _safe_rows(
        auth,
        "/rest/v1/academy_sessions",
        params={"select": "id,user_id,status,stage,mode,training_focus,interaction_mode,started_at,updated_at", "order": "updated_at.desc", "limit": "100"},
    )
    ai_today = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_usage_log",
        params={"select": "user_id,ai_role,model,calculated_cost_usd,credits_charged,created_at", "created_at": "gte." + datetime.now(timezone.utc).date().isoformat(), "order": "created_at.desc", "limit": "500"},
    )
    _metric_row(users, activity, sessions, ai_today)

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown("#### 최근 로그인 · 활동")
        display = []
        user_map = {str(u.get("user_id")): u for u in users}
        for row in activity[:12]:
            u = user_map.get(str(row.get("user_id")), {})
            display.append({
                "시간": _fmt_dt(row.get("created_at")),
                "사용자": u.get("display_name") or u.get("login_id") or "-",
                "앱": row.get("app_code"),
                "활동": row.get("event_code"),
                "결과": row.get("outcome"),
            })
        if display:
            st.dataframe(display, hide_index=True, use_container_width=True)
        else:
            st.caption("아직 활동 기록이 없습니다.")

    with right:
        st.markdown("#### 시스템 상태")
        runtime = _fetch_runtime(auth)
        if not runtime:
            st.info("09 마이그레이션 적용 후 AI 운영 상태가 표시됩니다.")
        else:
            st.write("AI 서비스", "● 정상 운영" if runtime.get("service_enabled") else "○ 정지")
            st.write("텍스트 AI", "ON" if runtime.get("text_enabled") else "OFF")
            st.write("음성 AI", "ON" if runtime.get("voice_enabled") else "OFF")
            st.write("AI 정식평가", "ON" if runtime.get("assessment_enabled") else "OFF")

        st.markdown("#### 현재 ACADEMY")
        current = [s for s in sessions if s.get("status") == "in_progress"][:8]
        if current:
            user_map = {str(u.get("user_id")): u for u in users}
            for s in current:
                u = user_map.get(str(s.get("user_id")), {})
                st.caption(
                    f"{u.get('display_name') or u.get('login_id') or '사용자'} · "
                    f"{s.get('stage') or '-'} · {s.get('mode') or '-'} · {_fmt_dt(s.get('updated_at'))}"
                )
        else:
            st.caption("현재 진행 중인 ACADEMY Session이 없습니다.")


def _account_filters(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    c1, c2, c3, c4 = st.columns([1.6, 1, 1, 1])
    search = c1.text_input("검색", placeholder="이름, ID, 소속", key="hw_admin_account_search")
    orgs = sorted({str(u.get("organization_name") or "") for u in users if u.get("organization_name")})
    positions = sorted({str(u.get("position_name") or "") for u in users if u.get("position_name")})
    org = c2.selectbox("소속", ["전체", *orgs], key="hw_admin_org_filter")
    position = c3.selectbox("직책", ["전체", *positions], key="hw_admin_position_filter")
    active = c4.selectbox("상태", ["전체", "활성", "비활성"], key="hw_admin_active_filter")

    q = search.strip().casefold()
    result = []
    for u in users:
        hay = " ".join(
            str(u.get(k) or "") for k in (
                "display_name", "login_id", "organization_name",
                "parent_organization_name", "position_name"
            )
        ).casefold()
        if q and q not in hay:
            continue
        if org != "전체" and u.get("organization_name") != org:
            continue
        if position != "전체" and u.get("position_name") != position:
            continue
        if active == "활성" and not u.get("is_active"):
            continue
        if active == "비활성" and u.get("is_active"):
            continue
        result.append(u)
    return result


def _open_selected_user(table_event: Any, filtered: list[dict[str, Any]]) -> bool:
    try:
        rows = table_event.selection.rows
    except Exception:
        rows = []
    if not rows:
        return False
    idx = int(rows[0])
    if 0 <= idx < len(filtered):
        st.session_state["hw_admin_selected_user_id"] = str(filtered[idx]["user_id"])
        st.session_state["hw_admin_user_page"] = "overview"
        st.rerun()
    return True


def _render_accounts(auth: HwarangAuthService, actor_id: str, users: list[dict[str, Any]]) -> None:
    selected_id = st.session_state.get("hw_admin_selected_user_id")
    if selected_id:
        selected = next((u for u in users if str(u.get("user_id")) == str(selected_id)), None)
        if selected:
            _render_user_detail(auth, actor_id, selected, users)
            return
        st.session_state.pop("hw_admin_selected_user_id", None)

    st.subheader("계정 · 권한")
    st.caption("행을 선택하면 같은 WORKSPACE 안에서 사용자 상세 페이지가 열립니다.")
    filtered = _account_filters(users)
    table = []
    for u in filtered:
        available = max(
            0,
            int(u.get("training_credit_balance") or 0)
            - int(u.get("training_credit_reserved") or 0),
        )
        alloc = int(u.get("training_credit_allocation") or 0)
        pct = round(available / alloc * 100) if alloc > 0 else 0
        state, _ = credit_display_state(pct, allocation_credits=alloc)
        table.append({
            "사용자": f"{u.get('display_name') or '-'} · {u.get('login_id') or '-'}",
            "소속 · 직책": f"{u.get('organization_name') or '-'} · {u.get('position_name') or '-'}",
            "계정": "활성" if u.get("is_active") else "비활성",
            "최근 로그인": _fmt_dt(u.get("last_login_at")),
            "최근 활동": u.get("recent_activity_code") or "-",
            "훈련 크레딧": f"{pct}% · {state}" if alloc > 0 else "미지급",
        })
    if not table:
        st.info("조건에 맞는 계정이 없습니다.")
        return

    event = st.dataframe(
        pd.DataFrame(table),
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="hw_admin_user_table",
    )
    _open_selected_user(event, filtered)


def _render_user_header(user: dict[str, Any]) -> None:
    if st.button("← 계정 목록", key="hw_admin_back_users"):
        st.session_state.pop("hw_admin_selected_user_id", None)
        st.rerun()
    name = user.get("display_name") or user.get("login_id") or "사용자"
    st.markdown(f"### {name}")
    st.caption(
        f"{user.get('login_id') or '-'} · {user.get('organization_name') or '-'} · "
        f"{user.get('position_name') or '-'}"
    )
    cols = st.columns(4)
    cols[0].metric("계정", "활성" if user.get("is_active") else "비활성")
    cols[1].metric("최근 로그인", _fmt_dt(user.get("last_login_at")))
    cols[2].metric("최근 활동", str(user.get("recent_activity_code") or "-"))
    cols[3].metric("현재 상태", "활동 중" if _active_recent(user.get("recent_seen_at")) else "비활동")


def _render_user_detail(
    auth: HwarangAuthService,
    actor_id: str,
    user: dict[str, Any],
    users: list[dict[str, Any]],
) -> None:
    _render_user_header(user)
    current = st.session_state.setdefault("hw_admin_user_page", "overview")
    page = st.segmented_control(
        "사용자 상세",
        ["overview", "permissions", "activity", "academy", "ai"],
        default=current,
        format_func=lambda x: {
            "overview": "개요",
            "permissions": "권한",
            "activity": "활동 기록",
            "academy": "ACADEMY",
            "ai": "AI 사용량",
        }[x],
        key="hw_admin_user_nav",
        label_visibility="collapsed",
    ) or current
    st.session_state["hw_admin_user_page"] = page

    uid = str(user["user_id"])
    if page == "overview":
        _user_overview(auth, uid, user)
    elif page == "permissions":
        _user_permissions(auth, actor_id, uid)
    elif page == "activity":
        _user_activity(auth, uid)
    elif page == "academy":
        _user_academy(auth, uid)
    else:
        _user_ai(auth, actor_id, uid)


def _user_overview(auth: HwarangAuthService, uid: str, user: dict[str, Any]) -> None:
    st.markdown("#### 최근 30일 요약")
    activity = _safe_rows(
        auth,
        "/rest/v1/hwarang_activity_log",
        params={"select": "id,event_code,app_code,outcome,created_at", "user_id": f"eq.{uid}", "order": "created_at.desc", "limit": "300"},
    )
    sessions = _safe_rows(
        auth,
        "/rest/v1/academy_sessions",
        params={"select": "id,status,mode,stage,started_at,ended_at", "user_id": f"eq.{uid}", "order": "started_at.desc", "limit": "100"},
    )
    cols = st.columns(4)
    cols[0].metric("기록된 활동", len(activity))
    cols[1].metric("ACADEMY Session", len(sessions))
    cols[2].metric("완료 Session", sum(1 for s in sessions if s.get("status") == "completed"))
    credit = get_training_credit_status(auth, uid)
    if credit and credit.allocation_credits > 0:
        state, _ = credit_display_state(credit.remaining_percent, allocation_credits=credit.allocation_credits)
        cols[3].metric("훈련 크레딧", f"{credit.remaining_percent:.0f}% · {state}")
    else:
        cols[3].metric("훈련 크레딧", "미지급")


def _user_permissions(auth: HwarangAuthService, actor_id: str, uid: str) -> None:
    snapshot = auth.admin_user_snapshot(actor_id, uid)
    refs = auth.admin_reference_data(actor_id)
    profile = snapshot["profile"]
    current_access = dict(snapshot.get("app_access") or {})
    current_permissions = set(snapshot.get("feature_permissions") or ())

    positions = [r for r in refs["positions"] if r.get("is_active", True)]
    orgs = [r for r in refs["organizations"] if r.get("is_active", True)]
    perms = list(refs["permissions"])

    pos_codes = [str(r["code"]) for r in positions]
    pos_labels = {str(r["code"]): str(r.get("display_name") or r["code"]) for r in positions}
    org_ids = [str(r["id"]) for r in orgs]
    org_labels = {
        str(r["id"]): f"{r.get('name') or r.get('code')} · {_UNIT_LABELS.get(str(r.get('unit_type') or ''), r.get('unit_type') or '')}"
        for r in orgs
    }

    with st.form(f"hw_admin_user_permissions_{uid}", clear_on_submit=False):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            display_name = st.text_input("이름", value=str(profile.get("display_name") or ""))
            role_codes = list(_ROLE_LABELS)
            current_role = str(profile.get("role") or "user")
            role = st.selectbox(
                "시스템 권한",
                role_codes,
                index=role_codes.index(current_role) if current_role in role_codes else 0,
                format_func=lambda x: _ROLE_LABELS[x],
            )
            is_active = st.checkbox("계정 활성", value=bool(profile.get("is_active")))
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

        st.markdown("##### 앱 접근권한")
        app_values: dict[str, bool] = {}
        cols = st.columns(3)
        for col, code in zip(cols, ("workspace", "calculator", "academy")):
            with col:
                app_values[code] = st.checkbox(
                    _APP_LABELS[code],
                    value=bool(current_access.get(code, False)),
                    key=f"hw_detail_app_{uid}_{code}",
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
            with st.expander(_APP_LABELS.get(app_code, app_code), expanded=(app_code == "academy")):
                cols = st.columns(2)
                for idx, item in enumerate(items):
                    code = str(item["permission_code"])
                    with cols[idx % 2]:
                        permission_values[code] = st.checkbox(
                            str(item.get("display_name") or code),
                            value=code in current_permissions,
                            key=f"hw_detail_perm_{uid}_{code}",
                            help=str(item.get("description") or "") or None,
                        )

        confirmed = st.checkbox("변경 내용을 확인했습니다.", key=f"hw_detail_confirm_{uid}")
        submitted = st.form_submit_button("변경사항 저장", type="primary", use_container_width=True)

    if submitted:
        if not confirmed:
            st.info("변경 내용을 확인한 뒤 확인란을 선택해 주세요.")
            return
        updated = auth.admin_apply_user_changes(
            actor_user_id=actor_id,
            target_user_id=uid,
            display_name=display_name,
            role=role,
            is_active=is_active,
            organization_unit_id=organization_unit_id,
            position_code=position_code,
            app_access=app_values,
            permissions=permission_values,
        )
        st.success("계정과 권한을 저장했습니다.")
        if uid == actor_id:
            state = st.session_state.get("hwarang_auth") or {}
            state["profile"] = updated["profile"]
            state["app_access"] = updated["app_access"]
            state["feature_permissions"] = updated["feature_permissions"]
            state["profile_checked_at"] = 0
            st.session_state["hwarang_auth"] = state
        st.rerun()


def _user_activity(auth: HwarangAuthService, uid: str) -> None:
    rows = _safe_rows(
        auth,
        "/rest/v1/hwarang_activity_log",
        params={
            "select": "id,app_code,event_code,feature_code,outcome,metadata,created_at",
            "user_id": f"eq.{uid}",
            "order": "created_at.desc",
            "limit": "500",
        },
    )
    if not rows:
        st.caption("활동 기록이 없습니다.")
        return
    table = [{
        "시간": _fmt_dt(r.get("created_at")),
        "앱": r.get("app_code"),
        "활동": r.get("event_code"),
        "기능": r.get("feature_code") or "-",
        "결과": r.get("outcome"),
    } for r in rows]
    st.dataframe(table, hide_index=True, use_container_width=True)


def _user_academy(auth: HwarangAuthService, uid: str) -> None:
    sessions = _safe_rows(
        auth,
        "/rest/v1/academy_sessions",
        params={
            "select": "id,case_id,status,stage,scenario_id,mode,difficulty,training_focus,interaction_mode,last_turn_no,started_at,ended_at,updated_at",
            "user_id": f"eq.{uid}",
            "order": "updated_at.desc",
            "limit": "200",
        },
    )
    assessments = _safe_rows(
        auth,
        "/rest/v1/academy_assessments",
        params={
            "select": "id,session_id,assessment_type,evaluator_type,framework_version,overall_score,grade,status,generated_at",
            "user_id": f"eq.{uid}",
            "order": "generated_at.desc",
            "limit": "200",
        },
    )
    c1, c2 = st.columns(2)
    c1.metric("Session", len(sessions))
    c2.metric("평가", len(assessments))
    st.markdown("##### 최근 Session")
    if sessions:
        st.dataframe(sessions, hide_index=True, use_container_width=True)
    else:
        st.caption("Session 기록이 없습니다.")
    st.markdown("##### 최근 평가")
    if assessments:
        st.dataframe(assessments, hide_index=True, use_container_width=True)
    else:
        st.caption("평가 기록이 없습니다.")


def _user_ai(auth: HwarangAuthService, actor_id: str, uid: str) -> None:
    credit = get_training_credit_status(auth, uid)
    if not credit:
        st.info("09 마이그레이션 적용 후 훈련 크레딧 관리가 활성화됩니다.")
        return

    state, _ = credit_display_state(
        credit.remaining_percent,
        allocation_credits=credit.allocation_credits,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("남은 이용량", f"{credit.remaining_percent:.0f}%")
    c2.metric("상태", state)
    c3.metric("예약 중", f"{credit.reserved_credits:,} credit")

    st.progress(max(0.0, min(1.0, credit.remaining_percent / 100.0)))

    with st.expander("훈련 크레딧 관리", expanded=True):
        operation = st.radio(
            "작업",
            ["grant", "revoke", "reset"],
            horizontal=True,
            format_func=lambda x: {"grant": "추가 지급", "revoke": "회수", "reset": "잔액 재설정"}[x],
            key=f"hw_credit_op_{uid}",
        )
        amount = st.number_input("크레딧", min_value=0, step=100, key=f"hw_credit_amount_{uid}")
        note = st.text_input("사유", placeholder="예: 이용권 구매 / 관리자 추가 지급", key=f"hw_credit_note_{uid}")
        if st.button("크레딧 적용", type="primary", key=f"hw_credit_apply_{uid}"):
            auth._request(
                "POST",
                "/rest/v1/rpc/admin_adjust_hwarang_ai_credits",
                admin=True,
                json={
                    "p_actor_user_id": actor_id,
                    "p_target_user_id": uid,
                    "p_operation": operation,
                    "p_amount": int(amount),
                    "p_note": note,
                },
            )
            st.success("훈련 크레딧을 반영했습니다.")
            st.rerun()

    usage = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_usage_log",
        params={
            "select": "ai_role,model,input_tokens,cached_tokens,output_tokens,credits_charged,calculated_cost_usd,status,latency_ms,created_at",
            "user_id": f"eq.{uid}",
            "order": "created_at.desc",
            "limit": "500",
        },
    )
    ledger = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_credit_ledger",
        params={
            "select": "entry_type,delta_credits,balance_after,allocation_after,note,created_at",
            "user_id": f"eq.{uid}",
            "order": "created_at.desc",
            "limit": "300",
        },
    )

    st.markdown("##### AI 사용량 원장")
    if usage:
        st.dataframe(usage, hide_index=True, use_container_width=True)
    else:
        st.caption("아직 실제 AI 사용 기록이 없습니다.")

    st.markdown("##### 크레딧 원장")
    if ledger:
        st.dataframe(ledger, hide_index=True, use_container_width=True)
    else:
        st.caption("크레딧 변동 기록이 없습니다.")


def _render_activity(auth: HwarangAuthService, actor_id: str, users: list[dict[str, Any]]) -> None:
    st.subheader("활동 기록")
    user_map = {str(u.get("user_id")): u for u in users}
    tab = st.segmented_control(
        "로그 종류",
        ["user", "admin"],
        default="user",
        format_func=lambda x: "사용자 활동" if x == "user" else "관리자 감사 로그",
        label_visibility="collapsed",
    )
    if tab == "admin":
        logs = auth.admin_audit_log(actor_id, limit=200)
        table = [{
            "시간": _fmt_dt(r.get("created_at")),
            "관리자": (user_map.get(str(r.get("actor_user_id"))) or {}).get("display_name") or r.get("actor_user_id"),
            "대상": (user_map.get(str(r.get("target_user_id"))) or {}).get("display_name") or r.get("target_user_id") or "-",
            "작업": r.get("action"),
        } for r in logs]
        st.dataframe(table, hide_index=True, use_container_width=True)
        return

    c1, c2, c3 = st.columns([1,1,1])
    app = c1.selectbox("앱", ["전체","workspace","calculator","academy","platform"])
    outcome = c2.selectbox("결과", ["전체","success","info","blocked","failed"])
    limit = c3.selectbox("표시", [100,200,500], index=1)

    params: dict[str, Any] = {
        "select": "id,user_id,app_code,event_code,feature_code,outcome,created_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if app != "전체":
        params["app_code"] = f"eq.{app}"
    if outcome != "전체":
        params["outcome"] = f"eq.{outcome}"
    rows = _safe_rows(auth, "/rest/v1/hwarang_activity_log", params=params)
    table = [{
        "시간": _fmt_dt(r.get("created_at")),
        "사용자": (user_map.get(str(r.get("user_id"))) or {}).get("display_name") or "-",
        "앱": r.get("app_code"),
        "활동": r.get("event_code"),
        "기능": r.get("feature_code") or "-",
        "결과": r.get("outcome"),
    } for r in rows]
    st.dataframe(table, hide_index=True, use_container_width=True)


def _render_academy(auth: HwarangAuthService, users: list[dict[str, Any]]) -> None:
    st.subheader("ACADEMY 관리")
    user_map = {str(u.get("user_id")): u for u in users}
    sessions = _safe_rows(
        auth,
        "/rest/v1/academy_sessions",
        params={"select": "id,user_id,status,stage,scenario_id,mode,training_focus,interaction_mode,last_turn_no,started_at,ended_at,updated_at", "order": "updated_at.desc", "limit": "500"},
    )
    assessments = _safe_rows(
        auth,
        "/rest/v1/academy_assessments",
        params={"select": "id,user_id,session_id,assessment_type,evaluator_type,overall_score,grade,status,generated_at", "order": "generated_at.desc", "limit": "500"},
    )
    tab = st.segmented_control(
        "ACADEMY 종류",
        ["sessions","assessments"],
        default="sessions",
        format_func=lambda x: "Session" if x == "sessions" else "평가 결과",
        label_visibility="collapsed",
    )
    rows = sessions if tab == "sessions" else assessments
    display = []
    for r in rows:
        item = dict(r)
        item["사용자"] = (user_map.get(str(r.get("user_id"))) or {}).get("display_name") or r.get("user_id")
        item.pop("user_id", None)
        display.append(item)
    st.dataframe(display, hide_index=True, use_container_width=True)


def _render_ai(auth: HwarangAuthService, users: list[dict[str, Any]]) -> None:
    st.subheader("AI 사용량 · 비용")
    runtime = _fetch_runtime(auth)
    if not runtime:
        st.info("09 마이그레이션 적용 후 AI 운영 대시보드가 활성화됩니다.")
        return
    user_map = {str(u.get("user_id")): u for u in users}
    usage = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_usage_log",
        params={"select": "user_id,ai_role,model,input_tokens,cached_tokens,output_tokens,credits_charged,calculated_cost_usd,status,created_at", "order": "created_at.desc", "limit": "1000"},
    )
    requests = _safe_rows(
        auth,
        "/rest/v1/hwarang_ai_request_registry",
        params={"select": "user_id,purpose,status,actual_credits,block_reason,created_at", "order": "created_at.desc", "limit": "500"},
    )

    cols = st.columns(4)
    cols[0].metric("AI 요청", len(usage))
    cols[1].metric("차감 크레딧", f"{sum(int(r.get('credits_charged') or 0) for r in usage):,}")
    cols[2].metric("예상 API 비용", f"${sum(float(r.get('calculated_cost_usd') or 0) for r in usage):,.4f}")
    cols[3].metric("차단/실패", sum(1 for r in requests if r.get("status") in ("blocked","failed")))

    by_user: dict[str, dict[str, Any]] = {}
    for r in usage:
        uid = str(r.get("user_id") or "")
        slot = by_user.setdefault(uid, {"requests":0,"credits":0,"cost":0.0})
        slot["requests"] += 1
        slot["credits"] += int(r.get("credits_charged") or 0)
        slot["cost"] += float(r.get("calculated_cost_usd") or 0)
    summary = [{
        "사용자": (user_map.get(uid) or {}).get("display_name") or uid,
        "호출": v["requests"],
        "훈련 크레딧": v["credits"],
        "예상비용(USD)": round(v["cost"], 6),
    } for uid, v in sorted(by_user.items(), key=lambda x: x[1]["cost"], reverse=True)]
    st.markdown("##### 사용자별")
    if summary:
        st.dataframe(summary, hide_index=True, use_container_width=True)
    else:
        st.caption("아직 실제 AI 호출 기록이 없습니다.")

    st.markdown("##### 차단 기록")
    blocked = [r for r in requests if r.get("status") in ("blocked","failed") or r.get("block_reason")]
    if blocked:
        for r in blocked[:100]:
            r["사용자"] = (user_map.get(str(r.get("user_id"))) or {}).get("display_name") or r.get("user_id")
        st.dataframe(blocked, hide_index=True, use_container_width=True)
    else:
        st.caption("차단 기록이 없습니다.")


def _render_settings(auth: HwarangAuthService, actor_id: str) -> None:
    st.subheader("시스템 설정")
    runtime = _fetch_runtime(auth)
    if not runtime:
        st.warning("먼저 Supabase에서 09_Admin_Operations_AI_Guardrails.sql을 적용해 주세요.")
        return

    st.markdown("#### AI 서비스")
    st.caption("API Key가 생겨도 이 스위치를 켜기 전에는 AI 호출이 허용되지 않습니다.")
    with st.form("hw_ai_runtime_settings"):
        service_enabled = st.toggle("AI 서비스", value=bool(runtime.get("service_enabled")))
        c1, c2, c3 = st.columns(3)
        text_enabled = c1.toggle("텍스트 AI", value=bool(runtime.get("text_enabled")))
        voice_enabled = c2.toggle("음성 AI", value=bool(runtime.get("voice_enabled")))
        assessment_enabled = c3.toggle("AI 정식평가", value=bool(runtime.get("assessment_enabled")))
        soft_limit_percent = st.slider(
            "이용량 주의 표시 기준",
            min_value=50,
            max_value=95,
            value=int(runtime.get("soft_limit_percent") or 80),
            step=5,
            help="사용자 이용을 막는 분당 제한이 아닙니다. 관리자/사용자에게 잔여 이용량 경고를 표시하는 기준입니다.",
        )
        contact_label = st.text_input(
            "이용량 추가 문의 문구",
            value=str(runtime.get("contact_label") or "박병선 팀장에게 이용량 추가 문의"),
        )
        contact_url = st.text_input(
            "문의 링크",
            value=str(runtime.get("contact_url") or ""),
        )
        saved = st.form_submit_button("AI 운영 설정 저장", type="primary", use_container_width=True)
    if saved:
        auth._request(
            "POST",
            "/rest/v1/rpc/admin_update_hwarang_ai_runtime",
            admin=True,
            json={
                "p_actor_user_id": actor_id,
                "p_service_enabled": service_enabled,
                "p_text_enabled": text_enabled,
                "p_voice_enabled": voice_enabled,
                "p_assessment_enabled": assessment_enabled,
                "p_soft_limit_percent": int(soft_limit_percent),
                "p_contact_label": contact_label,
                "p_contact_url": contact_url,
            },
        )
        st.success("AI 운영 설정을 저장했습니다.")
        st.rerun()

    st.markdown("#### 긴급 정지")
    st.caption("WORKSPACE/CALCULATOR/비-AI ACADEMY는 유지하고 외부 AI 호출만 차단합니다.")
    if runtime.get("service_enabled"):
        if st.button("AI 서비스 긴급 정지", type="secondary", use_container_width=True):
            auth._request(
                "POST",
                "/rest/v1/rpc/admin_update_hwarang_ai_runtime",
                admin=True,
                json={
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
            st.warning("AI 서비스를 정지했습니다.")
            st.rerun()
    else:
        st.info("현재 AI 서비스는 정지 상태입니다.")


def render(auth: HwarangAuthService) -> None:
    try:
        actor_id, _viewer = _require_actor(auth)
    except HwarangAuthError as exc:
        st.error(str(exc))
        return

    _top_header()
    page = _nav()
    try:
        users = _fetch_users(auth, actor_id)
        if page == "dashboard":
            _render_dashboard(auth, actor_id, users)
        elif page == "accounts":
            _render_accounts(auth, actor_id, users)
        elif page == "activity":
            _render_activity(auth, actor_id, users)
        elif page == "academy":
            _render_academy(auth, users)
        elif page == "ai":
            _render_ai(auth, users)
        else:
            _render_settings(auth, actor_id)
    except HwarangAuthError as exc:
        st.error(str(exc))
