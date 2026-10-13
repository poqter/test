"""Publication diagnostics must distinguish readiness from delivery, without AI."""
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest

_spec = importlib.util.spec_from_file_location('daily_audit', Path(__file__).parents[1] / '.github/scripts/hwarang_daily_briefing.py')
daily = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daily)

@pytest.mark.parametrize('status', ['no_snapshot', 'quality_hold', 'organization_approval_required'])
def test_publication_hold_is_unsuccessful_even_inside_daily_result(status):
    result = {'market': [{'profile': 'MARKET', 'status': status}], 'daily': {'status': 'completed'}}
    assert daily.configuration_failure(result, action='daily')

@pytest.mark.parametrize('status', ['published', 'disabled', 'manual_mode', 'before_publication_time'])
def test_expected_publication_outcomes_are_not_failures(status):
    assert not daily.configuration_failure([{'profile': 'NEWS', 'status': status}], action='publish')


def test_check_does_not_treat_historical_failures_as_current_failure():
    result = {'status': 'checked', 'settings': [{'required': True, 'ok': True}],
              'operations': {'jobs': [{'status': 'failed'}]}}
    assert not daily.configuration_failure(result, action='check')
    result['settings'][0]['ok'] = False
    assert daily.configuration_failure(result, action='check')

@pytest.mark.parametrize('details', [None, [], {'request_failure': None}, {'request_failure': []}])
def test_malformed_failure_metadata_cannot_mask_original_error(details):
    from modules.briefing.diagnostics import failure_diagnostic
    error = RuntimeError('Original generation error')
    error.diagnostics = details
    result = failure_diagnostic(error)
    assert result['failure_message'] == 'Original generation error'
    assert result['recovery_guidance']['retryable'] is None


def test_prepare_reads_one_consistent_policy_snapshot():
    from modules.briefing.scheduler import run_scheduled
    repo = Mock()
    repo.operating_policy.return_value = {'scheduled_generation_enabled': True,
        'automatic_publication_enabled': True, 'external_sharing_approved': False}
    repo.profiles.return_value = [{'profile_code': 'NEWS', 'is_enabled': True}]
    result = run_scheduled('prepare', datetime(2026, 10, 13, 21, 30, tzinfo=timezone.utc), repo)
    repo.operating_policy.assert_called_once_with()
    assert result['policy'] == repo.operating_policy.return_value
