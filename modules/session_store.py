"""Session-local drafts, revisions, results, review state, and scoped resets."""
from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any, MutableMapping

import streamlit as st


LEGACY_PREFIXES: dict[str, tuple[str, ...]] = {
    "analyzer": ("analyzer_",),
    "remodeling": ("rm_",),
    "deposit_vs_shortpay": ("hwarang_ds_", "ds_"),
    "renewal_vs_nonrenewal": ("rn_",),
    "inheritance_tax": ("it_",),
    "insurance_claim_guide": ("cg_",),
    "silson_generation_comparison": ("sc_",),
    "quick_calculators": ("a_",),
    "consultation_helper": ("b_",),
    "comparison_builder": ("c_",),
    "customer_materials": ("d_",),
    "education_center": ("e_",),
    "insurer_portal": ("f_", "home_insurer_"),
    "convention": ("convention_",),
    "summer": ("summer_",),
    "manager_results": ("manager_",),
    "commission_calculator": (
        "commission_", "manual_", "edit_", "save_edit_", "cancel_edit_",
        "auto_", "recruiter_", "review_include_", "excluded_", "unmatched_insurer_",
    ),
}

_SKIP_TOKENS = (
    "file", "upload", "editor", "_run", "_download", "_add_", "_remove_",
    "_delete_", "_generate_", "_apply_", "_reset", "_restore_", "_clear_",
    "_example", "cg_claim_", "_select_all", "_select_default", "_select_none",
    "_open", "_preview", "_approve", "_confirm", "_cancel", "_move_",
    "_help", "_calculate", "_recheck", "_claim_link", "_make_",
)
_AUTH_KEYS = frozenset({"password_correct", "login_user", "active_app"})


def _state(state: MutableMapping[str, Any] | None) -> MutableMapping[str, Any]:
    return st.session_state if state is None else state


def _key(kind: str, page: str) -> str:
    return f"hw.{kind}.{page}"


def _draft_envelope(page: str, state: MutableMapping[str, Any]) -> dict[str, Any]:
    key = _key("draft", page)
    current = state.get(key)
    if not isinstance(current, dict) or "fields" not in current:
        current = {"fields": {}, "input_revision": 0}
        state[key] = current
    return current


def get_draft(page: str, *, state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    """Return an isolated copy of the current page draft fields."""
    session = _state(state)
    return copy.deepcopy(_draft_envelope(page, session)["fields"])


def input_revision(page: str, *, state: MutableMapping[str, Any] | None = None) -> int:
    return int(_draft_envelope(page, _state(state))["input_revision"])


def commit_input(page: str, field: str, value: Any, *, state: MutableMapping[str, Any] | None = None) -> int:
    """Commit one field and invalidate result/export/review when it changed."""
    session = _state(state)
    envelope = _draft_envelope(page, session)
    if not _draftable(value):
        raise TypeError("Draft values must be JSON-like scalars, dates, lists, tuples, or string-keyed dictionaries.")
    old = envelope["fields"].get(field, object())
    if old != value:
        envelope["fields"][field] = copy.deepcopy(value)
        envelope["input_revision"] = int(envelope["input_revision"]) + 1
        invalidate_result(page, state=session)
    return int(envelope["input_revision"])


def save_result(page: str, payload: Any, *, rule_version: str = "legacy", state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    session = _state(state)
    previous = session.get(_key("result", page), {})
    result = {
        "payload": copy.deepcopy(payload),
        "input_revision": input_revision(page, state=session),
        "result_revision": int(previous.get("result_revision", 0)) + 1,
        "rule_version": rule_version,
        "stale": False,
    }
    session[_key("result", page)] = result
    session.pop(_key("review", page), None)
    session.pop(_key("export", page), None)
    return copy.deepcopy(result)


def get_result(page: str, *, state: MutableMapping[str, Any] | None = None) -> dict[str, Any] | None:
    value = _state(state).get(_key("result", page))
    return copy.deepcopy(value) if isinstance(value, dict) else None


def result_is_current(page: str, *, state: MutableMapping[str, Any] | None = None) -> bool:
    result = get_result(page, state=state)
    return bool(result and not result.get("stale") and result.get("input_revision") == input_revision(page, state=state))


def invalidate_result(page: str, *, state: MutableMapping[str, Any] | None = None) -> None:
    session = _state(state)
    result = session.get(_key("result", page))
    if isinstance(result, dict):
        result["stale"] = True
    session.pop(_key("review", page), None)
    session.pop(_key("export", page), None)


def mark_reviewed(page: str, *, state: MutableMapping[str, Any] | None = None) -> int:
    session = _state(state)
    if not result_is_current(page, state=session):
        raise ValueError("현재 입력과 일치하는 결과가 필요합니다.")
    result = session[_key("result", page)]
    review_revision = int(result["result_revision"])
    session[_key("review", page)] = {
        "input_revision": int(result["input_revision"]),
        "review_revision": review_revision,
    }
    return review_revision


def review_is_current(page: str, *, state: MutableMapping[str, Any] | None = None) -> bool:
    session = _state(state)
    review = session.get(_key("review", page))
    result = session.get(_key("result", page))
    return bool(
        isinstance(review, dict) and isinstance(result, dict)
        and result_is_current(page, state=session)
        and review.get("input_revision") == result.get("input_revision")
        and review.get("review_revision") == result.get("result_revision")
    )


def save_export(page: str, payload: bytes, *, state: MutableMapping[str, Any] | None = None) -> None:
    session = _state(state)
    if not review_is_current(page, state=session):
        raise ValueError("현재 결과를 검토한 뒤 내려받을 수 있습니다.")
    session[_key("export", page)] = {
        "bytes": bytes(payload),
        "input_revision": input_revision(page, state=session),
    }


def _draftable(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool, date, datetime)) or value is None:
        return True
    if isinstance(value, (list, tuple)):
        return all(_draftable(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _draftable(item) for key, item in value.items())
    return False


def save_legacy_draft(page: str, *, state: MutableMapping[str, Any] | None = None) -> None:
    """Capture only the explicit Stage 1 key families; uploads are excluded."""
    session = _state(state)
    prefixes = LEGACY_PREFIXES.get(page, ())
    if not prefixes:
        return
    fields: dict[str, Any] = {}
    for key in list(session):
        if not isinstance(key, str) or key.startswith("_ws_") or not key.startswith(prefixes):
            continue
        value = session[key]
        if any(token in key for token in _SKIP_TOKENS) or isinstance(value, (bytes, bytearray)):
            continue
        if _draftable(value):
            fields[key] = copy.deepcopy(value)
    if fields:
        envelope = _draft_envelope(page, session)
        changed = any(key not in envelope["fields"] or envelope["fields"][key] != value for key, value in fields.items())
        envelope["fields"].update(fields)
        if changed:
            envelope["input_revision"] = int(envelope["input_revision"]) + 1
            invalidate_result(page, state=session)
        # Keep the original compatibility key until all page widgets use callbacks.
        session["_draft_" + page] = copy.deepcopy(fields)


def restore_legacy_draft(page: str, *, state: MutableMapping[str, Any] | None = None) -> None:
    session = _state(state)
    legacy = session.pop("_draft_" + page, {})
    if isinstance(legacy, dict):
        _draft_envelope(page, session)["fields"].update(copy.deepcopy(legacy))
    for key, value in get_draft(page, state=session).items():
        if key.startswith(LEGACY_PREFIXES.get(page, ())):
            session.setdefault(key, copy.deepcopy(value))


def reset_page(page: str, *, state: MutableMapping[str, Any] | None = None) -> None:
    session = _state(state)
    prefixes = LEGACY_PREFIXES.get(page, ())
    scoped = (
        _key("draft", page), _key("result", page), _key("review", page),
        _key("upload", page), _key("export", page), _key("widget", page),
        "_draft_" + page,
    )
    for key in list(session):
        if key in scoped or any(isinstance(key, str) and key.startswith(item + ".") for item in scoped):
            del session[key]
            continue
        if isinstance(key, str) and (key.startswith(prefixes) or key.startswith(tuple("_ws_" + prefix for prefix in prefixes))):
            del session[key]
    transfer = session.get("hw.transfer")
    if isinstance(transfer, dict) and transfer.get("source_page") == page:
        del session["hw.transfer"]


def reset_all_work(*, state: MutableMapping[str, Any] | None = None) -> None:
    """Remove work data while preserving authentication and the current route."""
    session = _state(state)
    keep = {key: session[key] for key in _AUTH_KEYS if key in session}
    session.clear()
    session.update(keep)


def clear_session(*, state: MutableMapping[str, Any] | None = None) -> None:
    """Logout lifecycle: remove authentication and every work reference."""
    _state(state).clear()
