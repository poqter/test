"""Clear calculator inputs when the selected calculator changes."""
from __future__ import annotations

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


def activate(name, *, state=None):
    state = _state(state)
    state.pop(DRAFT_KEY, None)
    if state.get(ACTIVE_KEY) == name:
        return
    for key, value in list(state.items()):
        if _is_input(key, value) or key in EDITOR_KEYS or key == "hw.money_values":
            state.pop(key, None)
    state[ACTIVE_KEY] = name
