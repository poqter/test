"""Calculator-local input checkpoints, separate from transient widget lifetimes.

Only scalar/structured input state is saved. Uploads, output bytes, auth keys,
URLs and button events are never part of these drafts. Nothing is persisted
outside the current Streamlit session or sent to another tab.
"""
from __future__ import annotations
import copy
from datetime import date, datetime
from decimal import Decimal

INPUT_PREFIXES = ("cov_", "finance_", "pp_", "gift_", "wo_", "retirement_", "estate_", "a_", "_ws_a_", "ux_table_", "hw.table_base.", "hw.table_snapshot.", "hw.money_policy.", "hw.quick_money_migrated.")
EXCLUDED = ("_result", "_download", "_export", "_calculate", "_example", "_clear", "_help", "_review", "_customer", "_advisor", "_transfer", "_explain", "_pdf", "_excel", "_apply", "_submit")
EDITOR_KEYS = ("ux_table_carryforward", "ux_table_corporate_social", "ux_table_unlisted")
ACTION_KEYS = {"estate_confirm_note", "estate_cancel_note", "estate_replace_note"}
DRAFT_KEY = "hw.calculator_drafts.v1"
ACTIVE_KEY = "hw.calculator_draft_active"


def _state(state):
    if state is not None:
        return state
    import streamlit as st
    return st.session_state


def _is_input(key, value):
    return (isinstance(key, str) and key.startswith(INPUT_PREFIXES)
            and key not in EDITOR_KEYS and key not in ACTION_KEYS
            and not key.startswith("ux_table_reset_mode_")
            and not any(token in key for token in EXCLUDED)
            and not isinstance(value, (bytes, bytearray, memoryview)))


def capture(name, *, state=None):
    state = _state(state)
    if not name:
        return
    from modules.shared.runtime_cache import estimate_bytes
    fields = {k: copy.deepcopy(v) for k, v in list(state.items()) if _is_input(k, v)}
    # Canonical money is input, but contains keys for multiple pages. Small map.
    fields["hw.money_values"] = copy.deepcopy(state.get("hw.money_values", {}))
    snapshot = state.get("hw.table_snapshot." + name)
    if snapshot is not None:
        # Re-open an editor with its edited DataFrame as the new base. Never
        # write a saved edit-delta into the data_editor widget's Session State.
        fields["hw.table_base." + name] = copy.deepcopy(snapshot)
    if estimate_bytes(fields) > 4 * 1024 * 1024:
        return  # Never retain megabytes of unrelated intermediate data as a draft.
    drafts = state.setdefault(DRAFT_KEY, {})
    # Insertion order doubles as an LRU; keep the active calculator and cap
    # all checkpoint copies together, not only each individual checkpoint.
    drafts.pop(name, None)
    drafts[name] = fields
    while len(drafts) > 1 and estimate_bytes(drafts) > 16 * 1024 * 1024:
        drafts.pop(next(iter(drafts)))


def activate(name, *, state=None):
    state = _state(state)
    old = state.get(ACTIVE_KEY)
    if old == name:
        if "ux_table_reset_mode_" + name in state:
            return  # An explicit clear/example callback owns this rerun.
        for key, value in state.get(DRAFT_KEY, {}).get(name, {}).items():
            if key not in state:
                state[key] = copy.deepcopy(value)
        snapshot = state.get("hw.table_snapshot." + name)
        if snapshot is not None and not any(key in state for key in EDITOR_KEYS):
            state["hw.table_base." + name] = copy.deepcopy(snapshot)
        return
    # The latest render already checkpointed the prior calculator.
    for key, value in list(state.items()):
        if _is_input(key, value):
            state.pop(key, None)
    state.pop("hw.money_values", None)
    for key in EDITOR_KEYS:
        state.pop(key, None)
    for key, value in state.get(DRAFT_KEY, {}).get(name, {}).items():
        state[key] = copy.deepcopy(value)
    state[ACTIVE_KEY] = name
