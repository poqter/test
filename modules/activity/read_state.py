"""Short-lived, session-local read reuse for modal and input interactions."""
from copy import deepcopy
from time import monotonic
import streamlit as st

BACKGROUND = 'sales_background_reads'
RESUME = 'sales_resume_reads'

def identity():
    auth = st.session_state.get('hwarang_auth', {})
    return (auth.get('access_token'), deepcopy(auth.get('profile', {})))

def remember(db):
    if BACKGROUND not in st.session_state:
        st.session_state[BACKGROUND] = (identity(), monotonic(), deepcopy(db._reads))

def invalidate():
    st.session_state.pop(BACKGROUND, None)
    st.session_state.pop(RESUME, None)

def resume():
    snapshot = st.session_state.pop(BACKGROUND, None)
    if snapshot:
        st.session_state[RESUME] = snapshot

def consume():
    snapshot = st.session_state.pop(RESUME, None)
    if snapshot and snapshot[0] == identity() and monotonic() - snapshot[1] < 30:
        return snapshot[2]
    return None

def refresh(db, context, seconds=15):
    """Retain reads across input reruns, never across writes or scope changes."""
    now = monotonic()
    if getattr(db, '_resumed', False):
        db._resumed = False
    elif getattr(db, '_read_context', None) != context or now - getattr(db, '_read_at', 0) >= seconds:
        db._reads.clear()
        db._read_at = now
    db._read_context = context
