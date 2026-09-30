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
from modules.shared.session_store import clear_session, save_legacy_draft


def allowed_ids(role: str | None) -> list[str]:
    """Return enabled pages for *role* in registry order."""
    permitted = ROLE_PERMISSIONS.get(role or "", frozenset())
    return [app_id for app_id in APP_IDS if app_id in permitted and APP_BY_ID[app_id].enabled]


def normalize_route(page_id: str | None, role: str | None) -> str:
    if page_id == "home":
        return "home"
    if page_id in APP_BY_ID and APP_BY_ID[page_id].external_app_key:
        return "home"
    return page_id if page_id in allowed_ids(role) else "home"


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
    target = normalize_route(page_id, role)
    save_legacy_draft(str(session.get("active_app", "home")), state=session)
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


def dispatch(page_id: str, *, role: str | None = None) -> Any:
    """Recheck permission, lazily import the page, and invoke its entrypoint."""
    effective_role = role if role is not None else st.session_state.get("login_user")
    if page_id not in allowed_ids(effective_role):
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
        # Do not expose uploaded content, filenames, parser messages, or a traceback.
        reference = uuid4().hex[:8]
        frames = traceback.extract_tb(error.__traceback__)
        locations = " > ".join(f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames)
        # Log code locations only; exception messages can contain customer data.
        logging.getLogger(__name__).error(
            "PAGE_RUN_FAILED ref=%s page=%s type=%s locations=%s",
            reference, page_id, type(error).__name__, locations,
        )
        st.error(f"화면을 불러오지 못했습니다. 메뉴에서 다시 열어 주세요. 오류 번호: {reference}")
        return None


def logout(*, state: MutableMapping[str, Any] | None = None, rerun: Callable[[], Any] | None = None) -> None:
    session = st.session_state if state is None else state
    clear_session(state=session)
    if rerun is None and state is None:
        st.rerun()
    elif rerun is not None:
        rerun()
