from modules.activity.entry_runtime import entry_code
from modules.activity.runtime_metrics import measure
import streamlit as st
import pytest


def test_compiled_entry_reused_with_isolated_globals_and_deploy_invalidation(tmp_path):
    source = tmp_path/'entry.py'
    source.write_text("value = globals().get('value', 0) + 1")
    code = entry_code(source)
    assert entry_code(source) is code
    first, second = {}, {}
    exec(code, first)
    exec(code, second)
    assert first['value'] == second['value'] == 1
    source.write_text('value = 25')
    assert entry_code(source) is not code
    exec(entry_code(source), second)
    assert second['value'] == 25


def test_metrics_bounded_and_errors_remain_errors(monkeypatch):
    state = {}
    monkeypatch.setattr(st, 'session_state', state)
    for _ in range(105):
        with measure('context'):
            pass
    with pytest.raises(ValueError):
        with measure('record_write'):
            raise ValueError('sensitive error must not be stored')
    rows = state['calendar_runtime_metrics']
    assert len(rows) == 100
    assert set(rows[-1]) == {'stage', 'ms', 'ok'}
    assert rows[-1]['ok'] is False
    assert rows[-1]['ms'] >= 0
