"""Bounded session-local timings; never store tokens, parameters or business data."""
from contextlib import contextmanager
from time import perf_counter
import streamlit as st

@contextmanager
def measure(stage):
    started = perf_counter()
    ok = False
    try:
        yield
        ok = True
    finally:
        samples = st.session_state.setdefault('calendar_runtime_metrics', [])
        samples.append({'stage': stage, 'ms': round((perf_counter()-started)*1000, 2), 'ok': ok})
        del samples[:-100]
