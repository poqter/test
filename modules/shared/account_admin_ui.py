"""Super-admin account and permission management for HWARANG PLATFORM."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import streamlit as st

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


def _user_label(row: dict[str, Any]) -> str:
    name = str(row.get("display_name") or row.get("login_id") or "사용자")
    login_id = str(row.get("login_id") or "")
    org = str(row.get("organization_name") or "미지정")
    position = str(row.get("position_name") or "미지정")
    return f"{name} · {login_id} · {org} · {position}"


def render(auth: HwarangAuthService) -> None:
    viewer = st.session_state.get("login_profile") or {}
    actor_id = str(viewer.get("id") or "")
    if viewer.get("role") != "super_admin" or not actor_id:
        st.error("계정·권한 관리는 최고관리자만 이용할 수 있습니다.")
        return

    from .account_security import admin_recovery_dialog
    if st.button("비밀번호·이메일 복구", key="hw_admin_account_recovery"):
        admin_recovery_dialog(auth)
    st.subheader("계정·권한 관리")
    st.caption("사용자 계정, 소속·직책, 앱 접근권한과 주요 기능 권한을 관리합니다. 저장한 내용은 Supabase에 즉시 반영됩니다.")

    try:
        users = auth.admin_list_users(actor_id)
        refs = auth.admin_reference_data(actor_id)
    except HwarangAuthError as exc:
        st.error(str(exc))
        return

    if not users:
        st.info("관리할 사용자 계정이 없습니다.")
        return

    search = st.text_input("사용자 검색", placeholder="이름, 아이디, 소속 검색", key="hw_admin_user_search").strip().casefold()
    filtered = [
        row for row in users
        if not search or search in " ".join(
            str(row.get(key) or "") for key in (
                "display_name", "login_id", "organization_name", "parent_organization_name", "position_name"
            )
        ).casefold()
    ]
    if not filtered:
        st.info("검색 결과가 없습니다.")
        return

    by_id = {str(row["user_id"]): row for row in filtered if row.get("user_id")}
    selected_id = st.selectbox(
        "계정 선택",
        options=list(by_id),
        format_func=lambda uid: _user_label(by_id[uid]),
        key="hw_admin_selected_user",
    )
    selected = by_id[selected_id]

    try:
        snapshot = auth.admin_user_snapshot(actor_id, selected_id)
    except HwarangAuthError as exc:
        st.error(str(exc))
        return

    profile = snapshot["profile"]
    current_app_access = dict(snapshot.get("app_access") or {})
    current_permissions = set(snapshot.get("feature_permissions") or ())

    positions = [row for row in refs.get("positions", []) if row.get("is_active", True)]
    organizations = [row for row in refs.get("organizations", []) if row.get("is_active", True)]
    permissions = list(refs.get("permissions", []))

    position_codes = [str(row["code"]) for row in positions]
    position_labels = {str(row["code"]): str(row.get("display_name") or row["code"]) for row in positions}
    org_ids = [str(row["id"]) for row in organizations]
    org_labels = {
        str(row["id"]): f"{row.get('name') or row.get('code')} · {_UNIT_LABELS.get(str(row.get('unit_type') or ''), row.get('unit_type') or '')}"
        for row in organizations
    }

    role_codes = list(_ROLE_LABELS)
    current_role = str(profile.get("role") or "user")
    current_position = str(profile.get("position_code") or "fp")
    current_org = str(profile.get("organization_unit_id") or "")

    st.markdown("---")
    with st.form("hw_account_permission_form", clear_on_submit=False):
        top1, top2 = st.columns(2, gap="large")
        with top1:
            display_name = st.text_input("이름", value=str(profile.get("display_name") or ""), max_chars=60)
            role = st.selectbox(
                "시스템 권한",
                role_codes,
                index=role_codes.index(current_role) if current_role in role_codes else 0,
                format_func=lambda code: _ROLE_LABELS[code],
                help="관리자(admin)는 자동 부여되지 않으며 최고관리자가 직접 지정할 때만 사용합니다.",
            )
            is_active = st.checkbox("계정 활성", value=bool(profile.get("is_active")))
        with top2:
            organization_unit_id = st.selectbox(
                "소속",
                org_ids,
                index=org_ids.index(current_org) if current_org in org_ids else 0,
                format_func=lambda uid: org_labels.get(uid, uid),
            ) if org_ids else None
            position_code = st.selectbox(
                "직책",
                position_codes,
                index=position_codes.index(current_position) if current_position in position_codes else 0,
                format_func=lambda code: position_labels.get(code, code),
            ) if position_codes else current_position
            st.text_input("로그인 ID", value=str(profile.get("login_id") or ""), disabled=True)

        st.markdown("#### 앱 접근권한")
        app_cols = st.columns(3)
        app_values: dict[str, bool] = {}
        for col, app_code in zip(app_cols, ("workspace", "calculator", "academy")):
            with col:
                app_values[app_code] = st.checkbox(
                    _APP_LABELS[app_code],
                    value=bool(current_app_access.get(app_code, False)),
                    key=f"hw_admin_app_{selected_id}_{app_code}",
                )

        st.markdown("#### 세부 기능 권한")
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in permissions:
            grouped[str(item.get("app_code") or "기타")].append(item)

        permission_values: dict[str, bool] = {}
        for app_code in ("workspace", "calculator", "academy"):
            items = grouped.get(app_code, [])
            if not items:
                continue
            with st.expander(_APP_LABELS.get(app_code, app_code), expanded=True):
                cols = st.columns(2, gap="medium")
                for idx, item in enumerate(items):
                    code = str(item["permission_code"])
                    label = str(item.get("display_name") or code)
                    description = str(item.get("description") or "")
                    with cols[idx % 2]:
                        permission_values[code] = st.checkbox(
                            label,
                            value=code in current_permissions,
                            key=f"hw_admin_perm_{selected_id}_{code}",
                            help=description or None,
                        )

        confirmed = st.checkbox("변경 내용을 확인했습니다.", key=f"hw_admin_confirm_{selected_id}")
        submitted = st.form_submit_button("변경사항 저장", type="primary", use_container_width=True)

    if submitted:
        if not confirmed:
            st.info("변경 내용을 확인한 뒤 확인란을 선택해 주세요.")
            return
        try:
            updated = auth.admin_apply_user_changes(
                actor_user_id=actor_id,
                target_user_id=selected_id,
                display_name=display_name,
                role=role,
                is_active=is_active,
                organization_unit_id=organization_unit_id,
                position_code=position_code,
                app_access=app_values,
                permissions=permission_values,
            )
            st.success("계정과 권한을 저장했습니다. Supabase에 즉시 반영되었습니다.")
            if selected_id == actor_id:
                state = st.session_state.get("hwarang_auth") or {}
                state["profile"] = updated["profile"]
                state["app_access"] = updated["app_access"]
                state["feature_permissions"] = updated["feature_permissions"]
                state["profile_checked_at"] = 0
                st.session_state["hwarang_auth"] = state
                st.session_state["login_profile"] = updated["profile"]
                st.session_state["hw_app_access"] = updated["app_access"]
                st.session_state["hw_feature_permissions"] = set(updated["feature_permissions"])
            st.rerun()
        except HwarangAuthError as exc:
            st.error(str(exc))

    with st.expander("최근 관리자 변경 이력", expanded=False):
        try:
            logs = auth.admin_audit_log(actor_id, limit=50)
            if logs:
                user_names = {str(row.get("user_id")): str(row.get("display_name") or row.get("login_id") or row.get("user_id")) for row in users}
                st.dataframe(
                    [
                        {
                            "시간": row.get("created_at"),
                            "관리자": user_names.get(str(row.get("actor_user_id")), row.get("actor_user_id")),
                            "대상": user_names.get(str(row.get("target_user_id")), row.get("target_user_id")),
                            "작업": row.get("action"),
                        }
                        for row in logs
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("아직 변경 이력이 없습니다.")
        except HwarangAuthError as exc:
            st.caption(str(exc))
