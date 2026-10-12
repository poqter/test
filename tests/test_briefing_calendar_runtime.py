"""Empty optional GitHub variables must not stop free preparation or generation."""
from datetime import date, datetime, timezone

import pytest

from modules.briefing.business_calendar import calendar_rows
from modules.briefing.scheduler import run_scheduled


@pytest.mark.parametrize('raw', ['', ' ', '\n'])
def test_blank_optional_calendar_setting_uses_standard_holidays(monkeypatch, raw):
    monkeypatch.setenv('BRIEFING_EXTRA_HOLIDAYS_JSON', raw)
    rows = calendar_rows(date(2026, 10, 12))
    assert len(rows) == 40
    by_date = {row['day']: row for row in rows}
    assert by_date['2026-10-12']['is_business_day']
    assert not by_date['2026-10-09']['is_business_day']
    assert not by_date['2026-10-11']['is_business_day']


def test_prepare_with_empty_github_variable_makes_no_paid_request(monkeypatch):
    monkeypatch.setenv('BRIEFING_EXTRA_HOLIDAYS_JSON', '')
    monkeypatch.setattr('requests.sessions.Session.request',
                        lambda *args, **kwargs: pytest.fail('Unexpected network call'))
    class Repo:
        def sync_business_calendar(self, day): self.calendar = calendar_rows(day)
        def ai_generation_enabled(self): return False
        def operating_policy(self): return {'scheduled_generation_enabled': True}
        def profiles(self): return [{'profile_code': 'NEWS', 'is_enabled': True}]
    repo = Repo()
    result = run_scheduled('prepare', datetime(2026, 10, 12, 0, tzinfo=timezone.utc), repo)
    assert result['status'] == 'prepared'
    assert result['ai_generation_enabled'] is False
    assert result['policy']['scheduled_generation_enabled'] is True
    assert result['enabled'] == ['NEWS']
    assert len(repo.calendar) == 40
