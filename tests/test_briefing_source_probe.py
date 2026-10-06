from datetime import datetime, timezone
import json
from unittest.mock import patch

import pytest
import requests
from streamlit.testing.v1 import AppTest

from modules.briefing.config import DISCOVERY_LANES
from modules.briefing.direct_sources import DirectSourceSpec, MAX_FEED_BYTES, probe_direct_sources
from modules.briefing.gates import insurance_routing_evidence, route_profiles
from modules.briefing.models import PhaseBResult, SourceCandidate
from modules.briefing.normalize import visible_text
from modules.briefing.phase_b import _dedupe, candidate_diagnostic
from modules.briefing.publication import PublicationDateEnricher
from modules.briefing.runtime import _coverage_status
from tests.test_briefing_discovery_budget import ReplayClient, collect, response

NOW = datetime(2026, 10, 6, 10, tzinfo=timezone.utc)
SPEC = DirectSourceSpec('fsc_press', '금융위원회', 'https://www.fsc.go.kr/feed?fid=0111&token=secret', profile_hints=('INSURANCE','NEWS'))
RSS = b'''<rss><channel><item><title>insurance</title><link>https://www.fsc.go.kr/no010101/123</link><pubDate>Tue, 06 Oct 2026 09:00:00 GMT</pubDate><description><![CDATA[<p>body</p><img src="ga.png"/>]]></description></item></channel></rss>'''


class FeedResponse:
    def __init__(self, body=RSS, status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {'Content-Type':'application/rss+xml'}

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, *args): yield self.body
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('URL with token=secret must not be exported')


class FeedSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value


def probe(*responses, spec=SPEC, destination_check=lambda url: True):
    http = FeedSession(*responses)
    result = probe_direct_sources([spec], as_of=NOW, session=http, destination_check=destination_check)
    return result, http


def test_probe_success_has_dates_safe_endpoints_and_no_api_or_db():
    packet, http = probe(FeedResponse())
    detail = packet['direct_sources']['fsc_press']
    assert detail['status'] == 'ok' and detail['http_status'] == 200
    assert detail['fresh_candidates'] == detail['dated_candidates'] == 1
    assert detail['latest_published_at'] == '2026-10-06T09:00:00+00:00'
    assert packet['candidate_sample'][0]['description'] == 'body'
    assert 'secret' not in json.dumps(packet)
    assert 'fid=0111' in detail['configured_endpoint']
    assert http.calls[0][1]['allow_redirects'] is False
    assert packet['project_openai_api_calls'] == packet['db_writes'] == 0


@pytest.mark.parametrize('value,reason', [
    (FeedResponse(status=503),'HTTPError'),
    (FeedResponse(b'<rss>broken'),'ParseError'),
    (FeedResponse(b'<html><p>service unavailable</p></html>'),'not_rss_or_atom'),
    (FeedResponse(b'x'*(MAX_FEED_BYTES+1)),'feed_too_large'),
    (FeedResponse(b'<!DOCTYPE rss [<!ENTITY x "foo">]><rss/>'),'unsupported_xml_declaration'),
    (requests.Timeout('secret request URL'),'Timeout'),
    (ValueError('unexpected secret'),'ValueError'),
])
def test_probe_failure_is_specific_and_does_not_leak_response_or_exception(value, reason):
    packet, _ = probe(value)
    detail = packet['direct_sources']['fsc_press']
    assert detail['status'] == 'failed' and detail['failure_reason'] == reason
    assert 'secret' not in json.dumps(packet)


def test_empty_atom_is_distinguished_from_html_error():
    packet, _ = probe(FeedResponse(b'<feed xmlns="http://www.w3.org/2005/Atom"/>'))
    assert packet['direct_sources']['fsc_press']['status'] == 'empty_valid'


def test_public_redirect_is_rechecked_but_cross_publisher_not_requested():
    packet, http = probe(FeedResponse(status=302, headers={'Location':'https://evil.example/feed'}))
    assert len(http.calls) == 1
    assert packet['direct_sources']['fsc_press']['failure_reason'] == 'cross_publisher_redirect'
    packet, http = probe(FeedResponse(status=302, headers={'Location':'https://www.fsc.go.kr/rss'}), FeedResponse())
    assert len(http.calls) == 2 and packet['direct_sources']['fsc_press']['status'] == 'ok'


def test_private_destination_is_blocked_before_http():
    packet, http = probe(destination_check=lambda url: False)
    assert not http.calls
    assert packet['direct_sources']['fsc_press']['failure_reason'] == 'unsafe_destination'


@pytest.mark.parametrize('body,expected', [
    ('<img src="mega-ga-insurance.png"><script>보험 ga</script><p>가족관계 확인</p>',False),
    ('mega gas gaming',False),
    ('GA업계 모집 규제 변경',True),
    ('GA 채널 정책',True),
    ('새 보험금 지급 기준',True),
])
def test_insurance_routes_visible_article_text_not_attributes_or_substrings(body, expected):
    row = SourceCandidate('관련 소식','https://mois.go.kr/a','정부','direct_rss','official',description=body)
    assert ('INSURANCE' in route_profiles(row,'NEWS')) is expected
    diagnostic = candidate_diagnostic(row)
    assert bool(diagnostic['insurance_routing']['matched_token']) is expected


def test_html_text_is_bounded_and_routing_evidence_preserves_actual_trigger():
    assert visible_text('<style>ga</style><p>하나 &amp; 둘</p>') == '하나 & 둘'
    assert len(visible_text('x'*20000)) == 12000
    row = SourceCandidate('채널 변화','https://example.com/a','기관','fixture','news',description='GA업계 규제')
    assert insurance_routing_evidence(row)['matched_text'] == '채널 변화 ga업계 규제'


def test_cross_routed_news_does_not_establish_insurance_coverage():
    row = SourceCandidate('보험 관련 공공정책','https://mois.go.kr/a','행안부','direct_rss','official',
                          published_at=NOW,freshness_tier='core_window',routed_profiles={'INSURANCE','NEWS'},
                          metadata={'profile_hints':['NEWS']})
    phase = PhaseBResult(NOW,[row],[],[],{},source_health={'fsc':{'profiles':['INSURANCE'],'status':'failed'}})
    assert _coverage_status(phase,'INSURANCE',1) == 'insufficient'
    assert _coverage_status(phase,'NEWS',1) == 'degraded'


def test_dedupe_retains_profile_collection_provenance():
    a = SourceCandidate('정책','https://example.com/a','기관','fixture','official',metadata={'profile_hint':'INSURANCE'})
    b = SourceCandidate('정책','https://example.com/a','기관','fixture','official',metadata={'profile_hint':'NEWS'})
    assert _dedupe([a,b])[0].metadata['profile_hints'] == ['INSURANCE','NEWS']


def test_completed_and_nonfinal_searches_are_separate_but_both_reserve_budget():
    packet = response(2)
    packet['output'][1]['status'] = 'searching'
    packet['output'][1]['action']['sources'] = [{'title':'not final','url':'https://fsc.go.kr/not-final'}]
    result = collect(ReplayClient([packet]*4))
    budget = result.diagnostics['discovery_budget']
    assert budget['request_count'] == 3 and budget['observed_search_actions'] == 6
    assert budget['search_status_counts'] == {'completed':3,'nonfinal':3,'failed':0,'unknown':0}
    assert budget['requests'][0]['actions'][0]['queries'] == ['query']
    assert all(not row['source_candidates'] for row in budget['requests'])
    assert result.diagnostics['skipped_lanes'][0]['lane_code'] == DISCOVERY_LANES[3].lane_code


@pytest.mark.parametrize('url,status', [
    ('https://file.mk.co.kr/a.pdf','attachment_url'),
    ('https://knia.or.kr/file-manager/123','attachment_url'),
    ('https://korea.kr/briefing/pressReleaseList.do?repCode=a','listing_page'),
])
def test_known_attachment_and_listing_do_not_spend_metadata_http_budget(url,status):
    http = FeedSession()
    enricher = PublicationDateEnricher(session=http,destination_check=lambda url: True)
    assert enricher._fetch(url).status == status
    assert enricher.requests == 0 and not http.calls


def test_probe_ui_needs_no_paid_ack_or_model_and_rerun_does_not_repeat_http():
    app = AppTest.from_string('''
import os
import streamlit as st
from unittest.mock import patch
from modules.briefing.briefing_center import _render_generate_panel
st.session_state['login_profile']={'id':'fixture','role':'super_admin'}
def probe(specs):
    st.session_state['probe_calls']=st.session_state.get('probe_calls',0)+1
    return {'status':'direct_source_probe','configured_source_count':0,'project_openai_api_calls':0,'db_writes':0,'direct_sources':{}}
with patch.dict(os.environ,{'BRIEFING_DIRECT_SOURCES_JSON':'[]','OPENAI_API_KEY':'','BRIEFING_DISCOVERY_MODEL':''}), patch('modules.briefing.briefing_center.probe_direct_sources',side_effect=probe), patch('modules.briefing.briefing_center.generate_and_store_briefings',side_effect=AssertionError('paid API forbidden')):
    _render_generate_panel(object())
''').run()
    assert not app.exception and app.button[0].disabled
    app.button(key='hw_briefing_probe_sources').click().run()
    assert not app.exception and app.session_state['probe_calls'] == 1
    assert any(d.label == '직접 출처 점검 JSON 다운로드' for d in app.get('download_button'))
    app.run()
    assert not app.exception and app.session_state['probe_calls'] == 1


def test_old_empty_degraded_draft_cannot_be_published_from_ui():
    from tests.test_briefing_stage1_ui import _bundle
    bundle = _bundle()
    bundle['issues'] = []
    bundle['revision'].update({'coverage_status':'degraded','validation_status':'ok'})
    app = AppTest.from_string(f'''
from types import SimpleNamespace
from modules.briefing.briefing_center import _render_profile_detail
_render_profile_detail(SimpleNamespace(event_updates=lambda *a,**kw: []),'INSURANCE',{bundle!r},can_manage=True)
''').run()
    assert not app.exception and app.button[0].disabled
