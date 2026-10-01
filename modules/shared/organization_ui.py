"""Admin-only operational settings, separate from deferred account management."""
from __future__ import annotations
import json
import streamlit as st
from modules.shared.organization import active_profile, deployment_settings, save_profile, versions, MAX_CONFIG_BYTES


def render():
    if not st.session_state.get("password_correct") or st.session_state.get("login_user") != "Admin":
        st.error("운영 설정은 관리자만 이용할 수 있습니다.")
        return
    from modules.shell.app_registry import APPS
    from modules.shared.runtime_cache import statistics
    from modules.shared.build_info import BUILD_ID
    st.subheader("운영 설정")
    st.caption("공통 PDF 브랜드·사용 메뉴·수수료 기본값 관리 · 사용자 계정/비밀번호 설정은 변경하지 않습니다.")
    st.caption(f"배포 버전: {BUILD_ID}")
    settings = deployment_settings()
    profile = active_profile()
    revisions = versions()
    latest_revision = max(v["revision"] for v in revisions)
    if settings.get("db_path"):
        st.caption("명시적으로 지정한 운영 DB를 사용합니다. 이 경로의 영구 저장 보장은 서버 운영 설정에 따릅니다.")
    else:
        st.info("현재는 세션 임시 설정입니다. 재시작·로그아웃 후 보존되지 않습니다. 유지할 설정은 JSON으로 내려받아 보관하세요. 영구 적용은 운영 DB 또는 배포 설정 반영이 필요합니다.")
    with st.expander("저장한 설정 불러오기"):
        source = st.file_uploader("운영 설정 JSON", type=["json"], key="org_profile_upload")
        if source is not None and st.button("설정 파일 적용", key="org_profile_import"):
            try:
                if source.size > MAX_CONFIG_BYTES:
                    raise ValueError("설정 파일이 너무 큽니다.")
                candidate = json.loads(source.getvalue().decode("utf-8"))
                save_profile(candidate, role=st.session_state.get("login_user"), expected_revision=latest_revision)
                st.rerun()
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                st.error("올바른 화랑 운영 설정 파일인지 확인해 주세요.")
    with st.form("org_settings_form"):
        candidate = dict(profile)
        candidate["brand_name"] = st.text_input("공통 PDF 출력 브랜드명", value=profile["brand_name"], max_chars=100)
        c1, c2 = st.columns(2)
        candidate["header_color"] = c1.color_picker("헤더 색상", profile["header_color"])
        candidate["accent_color"] = c2.color_picker("포인트 색상", profile["accent_color"])
        options = {app.id: app.label for app in APPS if app.enabled}
        candidate["allowed_tools"] = st.multiselect("운영할 메뉴", list(options), default=profile["allowed_tools"], format_func=options.get)
        candidate["commission_default_payout_percent"] = st.number_input("수수료 기본 지급률 (%)", min_value=0.0, max_value=100.0, value=float(profile["commission_default_payout_percent"]), step=0.1, format="%.12g")
        candidate["payout_rule_label"] = st.text_input("지급 기준명", value=profile["payout_rule_label"], max_chars=100)
        from datetime import date
        candidate["effective_from"] = st.date_input("적용 시작일", date.fromisoformat(profile["effective_from"])).isoformat()
        confirmed = st.checkbox("현재 역할 권한은 유지하고 위 운영 설정을 적용합니다.")
        submitted = st.form_submit_button("운영 설정 저장")
    if submitted and not confirmed:
        st.info("변경 내용을 확인하고 적용 확인란을 선택해 주세요.")
    if submitted and confirmed:
        try:
            save_profile(candidate, role=st.session_state.get("login_user"), expected_revision=latest_revision)
            st.success("설정을 저장했습니다. 선택한 적용 시작일부터 반영됩니다.")
            st.rerun()
        except (ValueError, PermissionError) as error:
            st.error(str(error))
    data = json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("현재 운영 설정 저장", data, "hwarang_organization.json", "application/json")
    with st.expander("설정 변경 이력 · 처리 상태"):
        st.dataframe([{"버전": v["revision"], "적용일": v["effective_from"], "변경 역할": v["changed_by"], "변경 시각": v["changed_at"]} for v in revisions], hide_index=True)
        st.json(statistics())
