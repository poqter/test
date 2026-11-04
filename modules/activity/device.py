"""Only a revocable random handle leaves the server; tokens stay encrypted at rest."""
import base64
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from cryptography.fernet import Fernet, InvalidToken
from modules.shared.hwarang_auth import HwarangAuthError

DEVICE_FRONTEND = Path(__file__).with_name("device_bridge")
PATH = "/rest/v1/sales_devices"

def cipher(auth):
    key = hashlib.sha256(("hwarang.device.v1:" + auth.config.secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def digest(handle):
    return hashlib.sha256(handle.encode()).hexdigest()

def enroll(auth, state):
    handle = secrets.token_urlsafe(40)
    auth._request("POST", PATH, admin=True, json={"digest":digest(handle),"owner":state["profile"]["id"],
                  "secret":cipher(auth).encrypt(state["refresh_token"].encode()).decode()})
    st.session_state["device_handle"] = handle
    st.session_state["device_action"] = "store"

def revoke(auth, all_devices=False):
    state = st.session_state
    handle = state.get("device_handle")
    if all_devices:
        criteria = {"owner":"eq."+state["login_profile"]["id"]}
    elif handle:
        criteria = {"digest":"eq."+digest(handle)}
    else:
        return
    auth._request("DELETE", PATH, admin=True, params=criteria)

def synchronize(auth, authenticate):
    session = st.session_state
    action = session.get("device_action","read")
    restoring = not session.get("password_correct")
    result = None
    if restoring or action in ("store", "clear"):
        bridge = components.declare_component("workspace_device", path=str(DEVICE_FRONTEND))
        result = bridge(action=action, token=session.get("device_handle","") if action=="store" else "", key="hw_device_bridge", default=None)
    if action in ("store","clear"):
        if result and result.get("action")==action:
            session.pop("device_action",None)
            if action=="store" and result.get("token")!=session.get("device_handle"):
                st.warning("이 브라우저에서는 로그인 유지 정보를 저장할 수 없습니다.")
        return
    handle = session.get("device_handle")
    if restoring:
        if not result or result.get("action")!="read":return
        handle = result.get("token")
    if not isinstance(handle,str) or len(handle)!=54:return
    criteria={"digest":"eq."+digest(handle),"expires_at":"gt."+datetime.now(timezone.utc).isoformat()}
    rows=auth._request("GET",PATH,admin=True,params={**criteria,"select":"owner,secret,issued_at"})
    if not rows:
        if not restoring: session.clear()
        session["device_action"]="clear"
        st.rerun()
    row=rows[0]
    if restoring:
        try:
            token=cipher(auth).decrypt(row["secret"].encode()).decode()
            state=auth.refresh({"profile":{"id":row["owner"]},"authenticated_at":datetime.fromisoformat(row["issued_at"]).timestamp(),"refresh_token":token})
        except (InvalidToken,HwarangAuthError) as exc:
            if isinstance(exc,HwarangAuthError) and (not exc.status and "연결" in str(exc) or (exc.status or 0)>=500):raise
            session["device_action"]="clear"
            st.rerun()
        save_rotation(auth,handle,state)
        authenticate(auth,state)
        session["device_handle"]=handle
        session["device_restored"]=True

def save_rotation(auth,handle,state):
    auth._request("PATCH",PATH,admin=True,params={"digest":"eq."+digest(handle),"owner":"eq."+state["profile"]["id"]},
                  json={"secret":cipher(auth).encrypt(state["refresh_token"].encode()).decode()})
