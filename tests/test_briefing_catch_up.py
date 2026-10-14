"""Delayed, duplicate and partial deliveries with no external AI or database."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import importlib.util
from pathlib import Path
import pytest

from modules.briefing import scheduler as s
from test_briefing_release import bundle

DAY = '2026-10-14'

def at(clock):
    return datetime.fromisoformat(DAY + 'T' + clock + '+09:00')

class Repo:
    def __init__(self):
        self.saved = {}
        self.runs = {}
        self.paid = []
        self.publications = []
        self.policy = {'scheduled_generation_enabled': True, 'automatic_publication_enabled': True}
        self.ai = True
    def profiles(self):
        return [{'profile_code': c, 'is_enabled': True, 'run_mode': 'auto'} for c in ('MARKET','NEWS','INSURANCE')]
    def operating_policy(self): return self.policy
    def ai_generation_enabled(self): return self.ai
    def sync_business_calendar(self, day): pass
    def finish_stale_jobs(self, day, codes): pass
    def bundle_for_date(self, code, day, **kw):
        assert str(day) == DAY
        return self.saved.get(code)
    def daily_run_status(self, day, group): return self.runs.get(group, {})
    def claim_run(self, key, day, group, owner, retry=False):
        state = self.runs.get(group, {})
        if state.get('status') in ('completed','blocked','running') or state.get('attempts',0)>=2 or (state.get('attempts') and not retry):
            return {'claimed': False, 'status': state['status']}
        self.runs[group] = {'status': 'running', 'attempts': state.get('attempts',0)+1, 'checkpoint': state.get('checkpoint',{})}
        return {'claimed': True, 'checkpoint': self.runs[group]['checkpoint']}
    def save_run(self, key, owner, checkpoint, status='running'):
        self.runs[key.split(':')[-1]].update(status=status, checkpoint=checkpoint.copy())
    def reserve_request(self, day, kind): self.paid.append(kind)
    def publish_revision(self, briefing_id, revision_id):
        self.saved[briefing_id]['revision']['publication_status']='published'
        self.publications.append(briefing_id)

def edition(code, status='draft'):
    result = bundle(code, DAY)
    result['revision']['publication_status'] = status
    return result

@pytest.fixture
def generate(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('Unexpected network')))
    def run(**kw):
        kw['before_request']('analysis')
        repo = kw['repository']
        for code in kw['profile_codes']: repo.saved[code] = edition(code)
        kw['checkpoint'].pop('pending_request', None)
        kw['save_checkpoint'](kw['checkpoint'])
        return SimpleNamespace(profiles=[SimpleNamespace(profile_code=c) for c in kw['profile_codes']])
    call = Mock(side_effect=run)
    monkeypatch.setattr(s, 'generate_and_store_briefings', call)
    return call

@pytest.mark.parametrize('clock,count,published', [('06:30:00',0,[]), ('07:05:00',1,[]), ('07:31:00',2,['MARKET']), ('09:29:00',2,['NEWS','INSURANCE','MARKET'])])
def test_late_tick_performs_all_due_steps(generate, clock, count, published):
    repo = Repo()
    result = s.catch_up(repo, at(clock))
    assert generate.call_count == count
    assert repo.publications == published
    assert result['status'] == ('published' if published else 'before_publication_time')
    for call in generate.call_args_list:
        group = 'MARKET' if call.kwargs['profile_codes'] == ('MARKET',) else 'DAILY'
        assert call.kwargs['as_of'] == s.cutoff(at(clock).date(), group)

def test_repeated_ticks_reuse_paid_results_and_do_not_republish(generate):
    repo = Repo()
    for clock in ('09:29:00','09:47:00','10:07:00'):
        assert s.catch_up(repo, at(clock))['status']=='published'
    assert len(repo.paid)==2 and len(repo.publications)==3
    assert all(r['attempts']==1 for r in repo.runs.values())

def test_stored_drafts_without_run_ledger_are_published_without_ai(generate):
    repo=Repo();repo.saved={c:edition(c) for c in ('MARKET','NEWS','INSURANCE')}
    assert s.catch_up(repo, at('09:29:00'))['status']=='published'
    generate.assert_not_called();assert not repo.paid

def test_market_failure_does_not_block_daily_publication(generate):
    normal = generate.side_effect
    def fail_market(**kw):
        if kw['profile_codes']==('MARKET',): raise RuntimeError('Market unavailable before request')
        return normal(**kw)
    generate.side_effect=fail_market
    repo=Repo();result=s.catch_up(repo,at('09:29:00'))
    assert repo.publications==['NEWS','INSURANCE']
    assert result['status']=='incomplete'

@pytest.mark.parametrize('state', [{'status':'blocked','attempts':1}, {'status':'completed','attempts':1}, {'status':'failed','attempts':2}, {'status':'running','attempts':1}])
def test_existing_run_guards_prevent_duplicate_payment(generate,state):
    repo=Repo();repo.runs['MARKET']=state
    repo.saved={c:edition(c,'published') for c in ('NEWS','INSURANCE')}
    assert s.catch_up(repo,at('09:29:00'))['status']=='incomplete'
    generate.assert_not_called();assert not repo.paid

def test_partial_saved_daily_is_held_without_repaying_for_news(generate):
    repo=Repo();repo.saved={'NEWS':edition('NEWS'),'MARKET':edition('MARKET')}
    result=s.catch_up(repo,at('09:29:00'))
    assert result['generation']['DAILY']['reason']=='partial_saved_editions'
    generate.assert_not_called();assert repo.publications==['MARKET','NEWS']

def test_safe_failed_attempt_retries_once_after_0810(generate):
    repo=Repo();repo.runs['MARKET']={'status':'failed','attempts':1};repo.saved={c:edition(c,'published') for c in ('NEWS','INSURANCE')}
    s.catch_up(repo,at('08:05:00'));assert not repo.paid
    s.catch_up(repo,at('08:10:00'));s.catch_up(repo,at('08:27:00'))
    assert len(repo.paid)==1 and repo.runs['MARKET']['attempts']==2

def test_unknown_response_checkpoint_is_never_sent_again(generate):
    repo=Repo();repo.runs['MARKET']={'status':'failed','attempts':1,'checkpoint':{'pending_request':{'kind':'analysis'}}}
    repo.saved={c:edition(c,'published') for c in ('NEWS','INSURANCE')}
    s.catch_up(repo,at('09:29:00'))
    generate.assert_not_called();assert not repo.paid
    assert repo.runs['MARKET']['status']=='blocked'

@pytest.mark.parametrize('defect', ['hidden','quality','policy'])
def test_publication_gates_are_retained_without_regeneration(generate,defect):
    repo=Repo();repo.saved={c:edition(c) for c in ('MARKET','NEWS','INSURANCE')}
    if defect=='hidden': repo.saved['NEWS']['revision']['publication_status']='hidden'
    elif defect=='quality': repo.saved['NEWS']['revision']['coverage_status']='degraded'
    else: repo.policy['automatic_publication_enabled']=False
    assert s.catch_up(repo,at('09:29:00'))['status']=='incomplete'
    assert 'NEWS' not in repo.publications
    generate.assert_not_called()

def test_paused_generation_cannot_be_bypassed_by_new_tick(generate):
    repo=Repo();repo.policy['scheduled_generation_enabled']=False
    assert s.catch_up(repo,at('09:29:00'))['status']=='incomplete'
    generate.assert_not_called();assert not repo.paid

def test_one_publication_exception_does_not_hide_other_editions(generate):
    repo=Repo();repo.saved={c:edition(c) for c in ('MARKET','NEWS','INSURANCE')}
    publish=repo.publish_revision
    def fail_market(code,rev):
        if code=='MARKET':raise RuntimeError('DB publication error')
        publish(code,rev)
    repo.publish_revision=fail_market
    result=s.catch_up(repo,at('09:29:00'))
    assert repo.publications==['NEWS','INSURANCE']
    assert result['status']=='incomplete'
    generate.assert_not_called()

def test_clock_crossing_0800_publishes_newly_due_news(generate,monkeypatch):
    ticks=[at('07:59:00')]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return ticks[0].astimezone(tz or timezone.utc)
    monkeypatch.setattr(s,'datetime',Clock)
    normal=generate.side_effect
    def cross_deadline(**kw):
        result=normal(**kw);ticks[0]=at('08:01:00');return result
    generate.side_effect=cross_deadline
    repo=Repo()
    assert s.run_scheduled('catch_up',repo=repo)['status']=='published'
    assert len(repo.publications)==3

def test_final_delivery_controls_cli_success():
    spec=importlib.util.spec_from_file_location('catch_up_cli',Path(__file__).parents[1]/'.github/scripts/hwarang_daily_briefing.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    assert cli.configuration_failure({'status':'incomplete'},action='catch_up')
    assert not cli.configuration_failure({'status':'published','generation':{'status':'failed'}},action='catch_up')

def test_cron_events_use_catch_up_instead_of_original_stage():
    workflow=(Path(__file__).parents[1]/'.github/workflows/hwarang_daily_briefing.yml').read_text()
    assert 'BRIEFING_ACTION=catch_up' in workflow
    assert 'BRIEFING_ACTION=prepare' not in workflow
    assert 'cancel-in-progress: false' in workflow
