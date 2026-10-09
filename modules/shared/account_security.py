"""Supabase email recovery and account settings; no SMTP secret is needed here."""
from __future__ import annotations

import re
import time
import streamlit as st
from .hwarang_auth import HwarangAuthError, HwarangAuthService

WORKSPACE_URL = "https://hwarang-workspace.streamlit.app/"


def password_valid(value: str) -> bool:
    return 8 <= len(value) <= 128 and bool(re.search(r"[A-Za-z]", value)) and bool(re.search(r"\d", value))


def request_recovery(auth: HwarangAuthService, email: str) -> None:
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HwarangAuthError("등록된 이메일 주소를 입력해 주세요.")
    # GoTrue owns account enumeration protection and rate limits. Never look up
    # arbitrary login IDs using the service credential on this public surface.
    auth._request("POST", "/auth/v1/recover", params={"redirect_to": WORKSPACE_URL}, json={"email": email})


@st.dialog("비밀번호 찾기")
def recovery_dialog(auth: HwarangAuthService) -> None:
    st.write("가입할 때 등록한 이메일로 비밀번호 재설정 메일을 보내드립니다.")
    with st.form("hw_recovery_request"):
        email = st.text_input("등록 이메일", placeholder="name@example.com")
        sent = st.form_submit_button("재설정 메일 받기", use_container_width=True, type="primary")
    if sent:
        if time.time() - float(st.session_state.get("hw_recovery_sent_at", 0)) < 60:
            st.info("잠시 후 다시 요청해 주세요.")
            return
        try:
            request_recovery(auth, email)
            st.session_state["hw_recovery_sent_at"] = time.time()
            st.success("등록된 계정이 있다면 재설정 메일을 보냈습니다. 메일함과 스팸함을 확인해 주세요.")
        except HwarangAuthError:
            st.error("메일 요청을 처리하지 못했습니다. 이메일 형식을 확인하고 잠시 후 다시 시도해 주세요.")
    st.link_button("이메일을 사용할 수 없어요 · 관리자 문의", "https://open.kakao.com/o/sFxdv4Rf")


def render_recovery_entry(auth: HwarangAuthService) -> bool:
    """Only accept an explicitly recovery-scoped OTP; never create a login state.

    Verify on a button click, not a GET/render: mail scanners must not consume it.
    A dedicated query value is removed immediately after successful exchange.
    """
    raw = str(st.query_params.get("recovery_token", "") or "")
    recovery = st.session_state.get("hw_password_recovery")
    if not raw and not recovery:
        return False
    st.title("비밀번호 재설정")
    if not recovery:
        st.write("새 비밀번호를 설정하려면 이메일 인증을 확인해 주세요.")
        if st.button("인증 확인하고 계속", type="primary"):
            try:
                if not re.fullmatch(r"[A-Za-z0-9_-]{20,512}", raw):
                    raise HwarangAuthError("재설정 링크가 올바르지 않습니다.")
                data = auth._request("POST", "/auth/v1/verify", json={"token_hash": raw, "type": "recovery"})
                if not isinstance(data, dict) or not data.get("access_token") or not (data.get("user") or {}).get("id"):
                    raise HwarangAuthError("이메일 인증을 확인할 수 없습니다.")
                st.session_state["hw_password_recovery"] = {"access_token": data["access_token"],
                    "user_id": data["user"]["id"], "expires_at": time.time() + min(int(data.get("expires_in") or 600), 600)}
                st.query_params.clear()
                st.rerun()
            except HwarangAuthError:
                st.error("이미 사용했거나 만료된 링크입니다. 로그인 화면에서 재설정 메일을 다시 요청해 주세요.")
        if st.button("로그인 화면으로 · 메일 다시 요청"):
            st.query_params.clear(); st.session_state.pop("hw_password_recovery", None); st.rerun()
        return True
    if time.time() >= recovery["expires_at"]:
        st.session_state.pop("hw_password_recovery", None)
        st.error("인증 시간이 만료됐습니다. 재설정 메일을 다시 요청해 주세요.")
        if st.button("로그인 화면으로"):
            st.query_params.clear(); st.rerun()
        return True
    with st.form("hw_recovery_password"):
        password = st.text_input("새 비밀번호", type="password", help="8~128자, 영문과 숫자 포함")
        confirm = st.text_input("새 비밀번호 확인", type="password")
        submitted = st.form_submit_button("새 비밀번호 저장", type="primary", use_container_width=True)
    if submitted:
        if password != confirm or not password_valid(password):
            st.error("비밀번호 확인을 맞추고 영문·숫자를 포함해 8~128자로 입력해 주세요.")
            return True
        try:
            auth._request("PUT", "/auth/v1/user", access_token=recovery["access_token"], json={"password": password})
            try:
                auth._request("POST", "/auth/v1/logout", access_token=recovery["access_token"], params={"scope": "global"})
            except HwarangAuthError:
                pass  # Migration 19 independently invalidates old app identities.
            for key in ("hw_password_recovery", "hwarang_auth", "login_profile", "login_user"):
                st.session_state.pop(key, None)
            st.session_state["password_correct"] = False
            st.session_state["hw_account_flash"] = "비밀번호를 변경했습니다. 새 비밀번호로 로그인해 주세요."
            st.rerun()
        except HwarangAuthError:
            st.error("변경 결과를 확인하지 못했습니다. 새 비밀번호로 로그인해 보거나 재설정 메일을 다시 요청해 주세요.")
    return True


@st.dialog("내 계정", width="large")
def account_dialog(auth: HwarangAuthService) -> None:
    state = st.session_state.get("hwarang_auth") or {}
    profile = state.get("profile") or {}
    uid = str(profile.get("id") or "")
    if not uid:
        st.error("다시 로그인해 주세요."); return
    try:
        user = auth._request("GET", "/auth/v1/user", access_token=state.get("access_token"))
    except HwarangAuthError as exc:
        st.error(str(exc)); return
    st.write(f"**{profile.get('display_name') or ''} · {profile.get('login_id') or ''}**")
    st.write("등록 이메일: " + str(user.get("email") or "미등록"))
    st.caption("이 이메일을 현재 사용할 수 있는지 확인해 주세요. 가입 당시 인증 완료 표시만으로 실제 수신 여부를 알 수는 없습니다.")
    tabs = st.tabs(["비밀번호 변경", "이메일 변경"])
    with tabs[0], st.form("hw_account_password"):
        current = st.text_input("현재 비밀번호", type="password")
        password = st.text_input("새 비밀번호", type="password", help="8~128자, 영문·숫자 포함")
        confirm = st.text_input("새 비밀번호 확인", type="password")
        save = st.form_submit_button("비밀번호 변경", type="primary")
    if save:
        if password != confirm or not password_valid(password) or password == current:
            st.error("현재와 다른 새 비밀번호를 입력하고 확인란을 맞춰 주세요."); return
        try:
            verified = auth.sign_in(str(profile.get("login_id") or ""), current)
            auth._request("PUT", "/auth/v1/user", access_token=verified["access_token"], json={"password": password})
            try:
                auth._request("POST", "/auth/v1/logout", access_token=verified["access_token"], params={"scope": "global"})
            except HwarangAuthError:
                pass
            st.session_state.clear()
            st.session_state["hw_account_flash"] = "비밀번호를 변경했습니다. 새 비밀번호로 다시 로그인해 주세요."
            st.rerun()
        except HwarangAuthError as exc:
            st.error(str(exc))
    with tabs[1], st.form("hw_account_email"):
        st.caption("현재 비밀번호를 확인한 뒤 이메일 변경을 요청합니다. Supabase에서 발송한 인증 메일을 확인해야 변경이 완료됩니다.")
        current_email_password = st.text_input("현재 비밀번호", type="password", key="hw_email_current_password")
        email = st.text_input("새 이메일", placeholder="name@example.com")
        change = st.form_submit_button("이메일 변경 인증 요청")
    if change:
        try:
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
                raise HwarangAuthError("이메일 형식을 확인해 주세요.")
            verified = auth.sign_in(str(profile.get("login_id") or ""), current_email_password)
            auth._request("PUT", "/auth/v1/user", access_token=verified["access_token"],
                          params={"redirect_to": WORKSPACE_URL}, json={"email": email.strip().lower()})
            st.success("이메일 변경 인증을 요청했습니다. 현재·새 이메일로 받은 안내를 확인한 뒤 다시 로그인해 주세요.")
        except HwarangAuthError as exc:
            st.error(str(exc))


@st.dialog("관리자 계정 복구", width="large")
def admin_recovery_dialog(auth: HwarangAuthService) -> None:
    actor = st.session_state.get("login_profile") or {}
    try:
        auth._require_super_admin(str(actor.get("id") or ""))
        rows = auth.admin_list_users(str(actor["id"]))
    except HwarangAuthError as exc:
        st.error(str(exc)); return
    query = st.text_input("이름·아이디·소속 검색").strip().casefold()
    rows = [r for r in rows if query and query in " ".join(str(r.get(k) or "") for k in ("login_id", "display_name", "organization_name")).casefold()]
    by_id = {str(r["user_id"]): r for r in rows}
    selected = st.selectbox("복구할 계정", list(by_id), index=None,
        format_func=lambda key: " · ".join(str(by_id[key].get(k) or "") for k in ("display_name", "login_id", "organization_name", "position_name")))
    if not selected: return
    target = auth._profile_by_id(selected)
    if not target: return
    st.write("복구 대상: **" + str(target.get("display_name")) + " · " + str(target.get("login_id")) + "**")
    method = st.selectbox("본인 확인 방법", ["기존 등록 연락처로 통화", "대면 확인", "소속 책임자 확인"], index=None, key="hw_admin_verify_" + selected)
    new_email = st.text_input("본인이 사용할 복구 이메일", key="hw_admin_email_" + selected)
    confirm = st.text_input("대상 로그인 아이디를 다시 입력", key="hw_admin_confirm_" + selected)
    if st.button("해당 계정의 이메일 수정 후 복구 메일 보내기", type="primary", disabled=not (method and confirm == target.get("login_id") and new_email), key="hw_admin_recover_" + selected):
        try:
            auth._require_super_admin(str(actor["id"]))
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", new_email.strip()):
                raise HwarangAuthError("이메일 형식을 확인해 주세요.")
            auth._request("PUT", "/auth/v1/admin/users/" + selected, admin=True, json={"email": new_email.strip().lower(), "email_confirm": True})
            auth._request("POST", "/rest/v1/hwarang_account_recovery_audit", admin=True,
                json={"actor_id": actor["id"], "target_id": selected, "verification_method": method})
            request_recovery(auth, new_email)
            st.success("이메일을 수정하고 복구 메일을 요청했습니다. 비밀번호는 계정 소유자가 직접 설정합니다.")
        except HwarangAuthError as exc:
            st.error(str(exc))
