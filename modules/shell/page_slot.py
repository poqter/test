"""Separate page slots let navigation remove old content before slow reads."""
import streamlit as st


def page_slot(active):
    slots = (st.empty(), st.empty())
    index = st.session_state.get('hw_page_slot_index', 0)
    if st.session_state.get('hw_rendered_page', active) != active:
        index = 1 - index
    st.session_state['hw_rendered_page'] = active
    st.session_state['hw_page_slot_index'] = index
    # Never clear and refill the same slot in one run: Streamlit coalesces those
    # messages and keeps its stale children. Clear the other slot instead.
    slots[1 - index].empty()
    return slots[index].container()
