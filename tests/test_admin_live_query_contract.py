"""Exercise the live admin query against the repository's SQL column contract."""
from pathlib import Path
import re

import pytest
from streamlit.testing.v1 import AppTest

from modules.shared import admin_center_ui as ui
from modules.shared.hwarang_auth import HwarangAuthError

ROOT = Path(__file__).resolve().parents[1]


def _registry_columns():
    sql = (ROOT / 'supabase/migrations/09_Admin_Operations_AI_Guardrails.sql').read_text()
    body = re.search(r'create table if not exists public\.hwarang_ai_request_registry\s*\((.*?)\n\);', sql, re.S).group(1)
    columns = set(re.findall(r'^\s{4}(\w+)\s', body, re.M))
    for path in sorted((ROOT / 'supabase/migrations').glob('*.sql')):
        for alteration in re.findall(r'alter table public\.hwarang_ai_request_registry\b(.*?);', path.read_text(), re.S):
            columns.update(re.findall(r'add column if not exists\s+(\w+)', alteration))
    return columns


def test_ai_page_queries_existing_columns_and_renders_empty_state():
    columns = repr(_registry_columns())
    app = AppTest.from_string(f'''
from modules.shared.admin_center_ui import _render_ai
from modules.shared.hwarang_auth import HwarangAuthError
class Auth:
    def _request(self, method, path, **kwargs):
        if path.endswith('/hwarang_ai_request_registry'):
            unknown = set(kwargs['params']['select'].split(',')) - {columns}
            if unknown:
                raise HwarangAuthError('Unknown registry columns: ' + ','.join(sorted(unknown)))
        return []
_render_ai(Auth())
''').run()
    assert not app.exception
    assert len(app.metric) == 5
    assert any('차단/실패 기록이 없습니다' in c.value for c in app.caption)


def test_reference_reads_are_reused_and_refresh_after_mutation(monkeypatch):
    state = {}
    monkeypatch.setattr(ui.st, 'session_state', state)
    class Auth:
        def __init__(self): self.calls = []
        def _request(self, method, path, **kwargs):
            self.calls.append((method, path))
            return [{'is_active': True, 'monthly_ai_budget_usd': 100}]
    auth = Auth()
    for _ in range(2):
        ui._fetch_users(auth)
        ui._fetch_runtime(auth)
        ui._fetch_credit_policy(auth)
    assert len(auth.calls) == 3
    ui._safe_rpc(auth, 'admin_update_hwarang_ai_runtime', {})
    for reader in (ui._fetch_users, ui._fetch_runtime, ui._fetch_credit_policy):
        reader(auth)
    assert len(auth.calls) == 7


def test_failed_mutation_preserves_cached_read(monkeypatch):
    state = {}
    monkeypatch.setattr(ui.st, 'session_state', state)
    ui._cached_admin_read('fixture', 30, lambda: ['current'])
    class Auth:
        def _request(self, *args, **kwargs):
            raise HwarangAuthError('Fixture failure')
    with pytest.raises(HwarangAuthError):
        ui._safe_rpc(Auth(), 'admin_update_hwarang_credit_policy', {})
    assert ui._cached_admin_read('fixture', 30, lambda: ['replacement']) == ['current']
