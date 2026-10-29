from copy import deepcopy
from unittest.mock import Mock
import pytest
from modules.briefing.execution_policy import (token_exhausted_response,bounded_analysis_recovery,ANALYSIS_OUTPUT_TOKENS)
from modules.briefing.openai_discovery import OpenAIWebDiscoveryClient
from modules.briefing.discovery_budget import DiscoveryBudget
from modules.briefing.config import DISCOVERY_LANES


def incomplete():
    return {'provider_status':'incomplete','status':'incomplete','usage_logged':True,'usage_available':True,
            'charge_uncertain':False,'requested_max_output_tokens':12000,'usage':{'output_tokens':12000}}


def test_exhausted_paid_response_is_archived_and_retried_once():
    cached=incomplete();saved={'analysis_responses':{'MARKET':cached}}
    assert bounded_analysis_recovery(saved,'MARKET',cached,allowed=True)==48000
    assert 'MARKET' not in saved['analysis_responses']
    assert saved['incomplete_analysis_archive']['MARKET']==cached
    with pytest.raises(RuntimeError):bounded_analysis_recovery(saved,'MARKET',cached,allowed=True)
    assert ANALYSIS_OUTPUT_TOKENS==24000


@pytest.mark.parametrize('changes',[{'charge_uncertain':True},{'usage_logged':False},{'provider_status':'in_progress'},
    {'incomplete_details':{'reason':'content_filter'}},{'usage':{'output_tokens':11999}}])
def test_other_failures_never_authorize_a_new_paid_request(changes):
    cached={**incomplete(),**changes};assert not token_exhausted_response(cached)
    assert bounded_analysis_recovery({},'MARKET',cached,allowed=True) is None


def web_response(second='searching'):
    return {'id':'resp_test','status':'completed','model':'synthetic','usage':{'input_tokens':10,'output_tokens':20},
            'output':[{'type':'web_search_call','id':'a','status':'completed','action':{'type':'search','query':'one'}},
                      {'type':'web_search_call','id':'b','status':second,'action':{'type':'search','query':'two'}}]}


def test_unfinished_web_action_retrieves_once_then_uses_direct_feeds_only():
    client=OpenAIWebDiscoveryClient(api_key='synthetic',model='synthetic');client.http=Mock()
    client.http.post.return_value=Mock(status_code=200,json=Mock(return_value=web_response()))
    client.http.get.return_value=Mock(status_code=200,json=Mock(return_value=web_response()))
    logged=[];budget=DiscoveryBudget(on_response=logged.append)
    result=client.run_lane(DISCOVERY_LANES[0],budget=budget)
    assert client.http.post.call_count==client.http.get.call_count==1
    assert result.candidates==[] and not budget.can_request()
    assert logged[0]['direct_feed_fallback'] and logged[0]['usage']['search_actions']==2
    assert logged[0]['search_status_counts']['nonfinal']==1


def test_successful_reread_resumes_without_new_search():
    client=OpenAIWebDiscoveryClient(api_key='synthetic',model='synthetic');client.http=Mock()
    client.http.post.return_value=Mock(status_code=200,json=Mock(return_value=web_response()))
    client.http.get.return_value=Mock(status_code=200,json=Mock(return_value=web_response('completed')))
    budget=DiscoveryBudget();client.run_lane(DISCOVERY_LANES[0],budget=budget)
    assert budget.can_request() and not budget.requests[0]['direct_feed_fallback']
    assert client.http.post.call_count==client.http.get.call_count==1
