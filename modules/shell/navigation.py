"""Authorization-aware navigation with lazy page imports."""
from __future__ import annotations

import logging
import traceback
from uuid import uuid4
from pathlib import Path
from importlib import import_module
from typing import Any, Callable, MutableMapping

import streamlit as st

from modules.shell.app_registry import APP_BY_ID, APP_IDS, ROLE_PERMISSIONS
from modules.shared.permissions import WORKSPACE_APP_PERMISSION
from modules.shared.session_store import clear_session, save_legacy_draft


def allowed_ids(role: str | None) -> list[str]:
    """Return enabled pages after platform, app and feature authorization.

    When a HWARANG feature-permission set is present in session state it is the
    authoritative user-level gate. The legacy role map remains only as a safe
    fallback for non-authenticated tests and older local workflows.
    """
    feature_permissions = st.session_state.get("hw_feature_permissions")
    app_access = st.session_state.get("hw_app_access") or {}

    if feature_permissions is not None and st.session_state.get("password_correct"):
        allowed_codes = set(feature_permissions)
        result: list[str] = []
        for app_id in APP_IDS:
            spec = APP_BY_ID[app_id]
            if not spec.enabled:
                continue
            if app_id == "quick_calculators":
                if app_access.get("calculator", False):
                    result.append(app_id)
                continue
            if app_id == "academy":
                if app_access.get("academy", False):
                    result.append(app_id)
                continue
            required = WORKSPACE_APP_PERMISSION.get(app_id)
            if required is None or required in allowed_codes:
                result.append(app_id)
        from modules.shared.organization import permitted_tools
        return permitted_tools(result)

    permitted = ROLE_PERMISSIONS.get(role or "", frozenset())
    from modules.shared.organization import permitted_tools
    return permitted_tools([app_id for app_id in APP_IDS if app_id in permitted and APP_BY_ID[app_id].enabled])


def normalize_route(page_id: str | None, role: str | None, *, allowed: list[str] | None = None) -> str:
    if page_id == "home":
        return "home"
    if page_id in APP_BY_ID and APP_BY_ID[page_id].external_app_key:
        return "home"
    permitted = allowed if allowed is not None else allowed_ids(role)
    return page_id if page_id in permitted else "home"


def navigate(
    page_id: str,
    mode: str | None = None,
    *,
    state: MutableMapping[str, Any] | None = None,
    rerun: Callable[[], Any] | None = None,
) -> str:
    """Save the current draft and move to an authorized page.

    Invalid and unauthorized destinations resolve to ``home``.  ``mode`` is a
    small Stage 2 adapter for direct links; individual pages decide when to
    consume ``hw.ui.target_mode``.
    """
    session = st.session_state if state is None else state
    role = session.get("login_user")
    target = normalize_route(page_id, role, allowed=session.get("ws_allowed_ids"))
    save_legacy_draft(str(session.get("active_app", "home")), state=session)
    from modules.shared.runtime_cache import clear_scope
    old_page = str(session.get("active_app", "home"))
    if old_page != target:
        clear_scope("parse:" + old_page + ":", state=session)
    session["active_app"] = target
    if mode and target != "home":
        session["hw.ui.target_mode"] = {"page": target, "mode": mode}
    else:
        session.pop("hw.ui.target_mode", None)
    if target != "home":
        recent = [item for item in session.get("hw.ui.recent", session.get("sig_recent", [])) if item != target]
        session["hw.ui.recent"] = [target, *recent][:4]
        session["sig_recent"] = list(session["hw.ui.recent"])
    if rerun is None and state is None:
        st.rerun()
    elif rerun is not None:
        rerun()
    return target


def dispatch(page_id: str, *, role: str | None = None, allowed: list[str] | None = None) -> Any:
    """Recheck permission, lazily import the page, and invoke its entrypoint."""
    effective_role = role if role is not None else st.session_state.get("login_user")
    permitted = allowed if allowed is not None else allowed_ids(effective_role)
    if page_id not in permitted:
        st.session_state["active_app"] = "home"
        return None
    spec = APP_BY_ID[page_id]
    if spec.external_app_key:
        st.session_state["active_app"] = "home"
        return None
    try:
        module = import_module(spec.module_path)
        entrypoint = getattr(module, spec.entrypoint)
        return entrypoint()
    except Exception as error:
        from modules.shared.error_reporting import record_error, user_message
        reference = record_error(error, page_id)
        st.error(user_message(reference))
        return None


def logout(*, state: MutableMapping[str, Any] | None = None, rerun: Callable[[], Any] | None = None) -> None:
    session = st.session_state if state is None else state
    clear_session(state=session)
    if rerun is None and state is None:
        st.rerun()
    elif rerun is not None:
        rerun()
