from copy import deepcopy
import json
from modules.briefing.diagnostics import ENGINE_VERSION

import pytest
from streamlit.testing.v1 import AppTest

from modules.briefing.openai_analysis import OpenAIAnalysisClient, BriefingAnalysisError
from tests.test_briefing_openai_analysis_contract import FakeResponse, FakeSession
from tests.test_briefing_phase_c import _event


@pytest.mark.parametrize("failure", ["incomplete", "schema", "event_key", "invalid_json"])
def test_analysis_failure_keeps_observed_usage_and_output_for_offline_review(failure):
    class Response(FakeResponse):
        def json(self):
            data = deepcopy(super().json())
            if failure == "incomplete":
                data["status"] = "incomplete"
            else:
                block = data["output"][0]["content"][0]
                parsed = json.loads(block["text"])
                if failure == "schema":
                    parsed["events"][0]["communication_state"] = "invented_state"
                if failure == "event_key":
                    parsed["events"][0]["event_key"] = "unrequested"
                block["text"] = "not JSON" if failure == "invalid_json" else json.dumps(parsed)
            return data
    class Session(FakeSession):
        def post(self, *args, **kwargs):
            return Response()
    records = []
    client = OpenAIAnalysisClient(api_key="fixture-secret", model="fixture", on_response=records.append)
    client.http = Session()
    with pytest.raises(BriefingAnalysisError) as caught:
        client.analyze("NEWS", [_event("e1", "정부 정책", "NEWS", 2)])
    assert len(records) == 1 and records[0]["usage"]["input_tokens"] == 10
    details = caught.value.diagnostics["analysis_response"]
    assert details["requested_event_keys"] == ["e1"]
    if failure != "incomplete":
        assert details["output_text_sample"] and details["status"] == "validation_failed"
    assert "fixture-secret" not in json.dumps(details)


def test_failed_generation_download_keeps_partial_diagnostics_and_rerun_does_not_generate():
    app = AppTest.from_string("""
import os
import streamlit as st
from unittest.mock import patch
from modules.briefing.runtime import BriefingRunError
from modules.briefing.briefing_center import _render_generate_panel
st.session_state['login_profile']={'id':'fixture', 'role':'super_admin'}
def fail(**kwargs):
    st.session_state['fixture_calls']=st.session_state.get('fixture_calls',0)+1
    raise BriefingRunError('Shared Discovery hard limit exceeded', {'stage':'web_discovery','discovery_requests':[{'usage':{'search_actions':7}}]})
env={'SUPABASE_URL':'https://fixture.supabase.co','SUPABASE_SECRET_KEY':'fixture-secret','OPENAI_API_KEY':'fixture-secret','BRIEFING_DISCOVERY_MODEL':'fixture','BRIEFING_DIRECT_SOURCES_JSON':'[]'}
with patch.dict(os.environ,env), patch('modules.briefing.briefing_center.generate_and_store_briefings',side_effect=fail):
    _render_generate_panel(object())
""").run()
    assert not app.exception and app.button[0].disabled
    assert any(ENGINE_VERSION in c.value for c in app.caption)
    assert any("API 호출 없음" in d.label for d in app.get("download_button"))
    app.checkbox[0].check().run()
    app.button[0].click().run()
    assert not app.exception and app.session_state['fixture_calls'] == 1
    packet = app.session_state['hw_briefing_last_diagnostic']
    assert packet['diagnostics']['discovery_requests'][0]['usage']['search_actions'] == 7
    assert 'fixture-secret' not in json.dumps(packet)
    assert any("이번 실행 전체 진단" in d.label for d in app.get("download_button"))
    app.run()
    assert app.session_state['fixture_calls'] == 1


def test_deployment_integrity_warning_disables_paid_generation_but_keeps_free_download():
    app = AppTest.from_string("""
import os
import streamlit as st
from unittest.mock import patch
from modules.briefing.briefing_center import _render_generate_panel
st.session_state['login_profile']={'id':'fixture', 'role':'super_admin'}
env={'SUPABASE_URL':'https://fixture.supabase.co','SUPABASE_SECRET_KEY':'fixture','OPENAI_API_KEY':'fixture','BRIEFING_DISCOVERY_MODEL':'fixture','BRIEFING_DIRECT_SOURCES_JSON':'[]'}
with patch.dict(os.environ,env), patch('modules.briefing.preflight.build_info',return_value={'code_matches_release':False}):
    _render_generate_panel(object())
""").run()
    assert not app.exception
    app.checkbox[0].check().run()
    assert app.button[0].disabled
    assert any("배포 파일" in e.value for e in app.error)
    assert any("API 호출 없음" in d.label for d in app.get("download_button"))
