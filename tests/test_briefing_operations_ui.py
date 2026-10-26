"""Real Streamlit button/rerun tests; all feed, DB and reader calls are mocked."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from modules.briefing import direct_sources

PROBE = {
    'status': 'direct_source_probe', 'generated_at': '2026-10-12T05:00:00+00:00',
    'project_openai_api_calls': 0, 'db_writes': 0, 'configured_source_count': 1,
    'direct_sources': {'SYNTHETIC': {'status': 'ok', 'dated_candidates': 8,
                                  'fresh_candidates': 6}},
    'candidate_sample': [],
}

SCRIPT = '''
import streamlit as st
from modules.briefing.operations_ui import render_operations
class ReadOnlyRepo:
    def retention_status(self): return {}
    def bundle_for_date(self,*args,**kwargs):return None
    def ai_generation_enabled(self): return False
    def operation_status(self, day): return {'runs': [], 'jobs': []}
    def cost_status(self):
        zero = {'requests':0,'search_actions':0,'input_tokens':0,'output_tokens':0,
                'estimated_known_usd':0,'unknown_cost_requests':0,
                'charge_uncertain_requests':0,'actual_known_usd':0}
        return {'today':zero,'month':zero}
    def operating_policy(self): return {}
    def verified_business_days(self, code): return 0
    def public_endpoint_ready(self):
        st.session_state['reader_checks'] = st.session_state.get('reader_checks',0)+1
        return True
st.session_state.setdefault('login_profile', {'id':'synthetic','role':'super_admin'})
render_operations(ReadOnlyRepo())
'''


@pytest.fixture
def feed_probe(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request',
                        Mock(side_effect=AssertionError('Unexpected real HTTP')))
    monkeypatch.setattr(direct_sources, 'load_direct_source_specs_from_env', lambda: [])
    probe = Mock(return_value=deepcopy(PROBE))
    monkeypatch.setattr(direct_sources, 'probe_direct_sources', probe)
    return probe


def click(app, label):
    return next(button for button in app.button if button.label == label).click().run()


@pytest.mark.parametrize('status,attempts,label,disabled',[
    ('failed',1,'중단된 브리핑 이어서 생성',False),
    ('failed',2,'중단된 브리핑 이어서 생성',True),
    ('blocked',1,'오늘 브리핑 생성',True),
])
def test_generation_recovery_button_respects_daily_limits(monkeypatch,status,attempts,label,disabled):
    from datetime import datetime, timezone
    from modules.briefing import briefing_center as center
    from modules.briefing import preflight, scheduler
    monkeypatch.setattr(center,'_can_manage',lambda:True)
    monkeypatch.setattr(center,'_clear_read_caches',lambda:None)
    monkeypatch.setattr(preflight,'run_runtime_preflight',lambda **kwargs:[])
    monkeypatch.setattr(scheduler,'cutoff',lambda day,group:datetime(2000,1,1,tzinfo=timezone.utc))
    generate=Mock(return_value={'status':'completed'})
    monkeypatch.setattr(center,'generate_group',generate)
    script='''
import streamlit as st
from unittest.mock import Mock
from modules.briefing.briefing_center import _render_generate_panel
st.session_state.setdefault('login_profile',{'id':'synthetic-manager','role':'super_admin'})
repo=Mock()
repo.profiles.return_value=[]
repo.ai_generation_enabled.return_value=True
repo.daily_run_status.return_value=RUN_STATUS
_render_generate_panel(repo)
'''.replace('RUN_STATUS',repr({'status':status,'attempts':attempts}))
    app=AppTest.from_string(script).run()
    assert not app.exception
    button=next(b for b in app.button if b.key=='hw_briefing_generate_today')
    assert button.label==label and button.disabled==disabled
    if not disabled:
        button.click().run()
        assert not app.exception
        generate.assert_called_once()
        assert generate.call_args.kwargs['retry'] is True
    else:generate.assert_not_called()


def test_feed_button_displays_diagnostics_without_crashing(feed_probe):
    app = AppTest.from_string(SCRIPT).run()
    click(app, '언론사 피드 연결 확인')
    assert not app.exception and not app.error
    assert app.dataframe[0].value.iloc[0]['피드'] == 'SYNTHETIC'
    assert app.get('download_button')
    assert any(button.label == '고객 공유 페이지 연결 확인' for button in app.button)
    assert any(button.label == '운영 정책 저장' for button in app.button)
    feed_probe.assert_called_once()


def test_feed_result_survives_rerun_and_other_button(feed_probe):
    app = AppTest.from_string(SCRIPT).run()
    click(app, '언론사 피드 연결 확인')
    app.run()
    click(app, '고객 공유 페이지 연결 확인')
    assert not app.exception and not app.error
    assert len(app.dataframe) == 1
    assert '고객 읽기 페이지가 연결됐습니다.' in [item.value for item in app.success]
    assert app.session_state['reader_checks'] == 1
    feed_probe.assert_called_once()


def test_failed_probe_leaves_other_controls_usable(feed_probe):
    feed_probe.side_effect = ValueError('synthetic invalid configuration')
    app = AppTest.from_string(SCRIPT).run()
    click(app, '언론사 피드 연결 확인')
    assert not app.exception
    assert len(app.error) == 1
    assert not app.dataframe
    click(app, '고객 공유 페이지 연결 확인')
    assert not app.exception
    assert '고객 읽기 페이지가 연결됐습니다.' in [item.value for item in app.success]


def test_failed_refresh_does_not_show_old_probe_as_current(feed_probe):
    app = AppTest.from_string(SCRIPT).run()
    click(app, '언론사 피드 연결 확인')
    feed_probe.side_effect = ValueError('synthetic invalid configuration')
    click(app, '언론사 피드 연결 확인')
    assert not app.exception
    assert len(app.error) == 1
    assert not app.dataframe

