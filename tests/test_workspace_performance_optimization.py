from pathlib import Path
from modules.briefing.repository import BriefingRepository
ROOT=Path(__file__).resolve().parents[1]
class Repo(BriefingRepository):
    def __init__(self): self.calls=[]
    def _request(self,method,path,*,params=None,json=None,prefer=None):
        self.calls.append((method,path,dict(params or {})))
        if path.endswith('/hwarang_briefings'):
            if str((params or {}).get('profile_code','')).startswith('in.'):
                return [{'id':'b1','profile_code':'NEWS','briefing_date':'2026-10-07','briefing_type':'MORNING','current_published_revision_id':'r1','created_at':'x'}]
            return [{'id':'b1','profile_code':'NEWS','briefing_date':'2026-10-07','briefing_type':'MORNING','current_published_revision_id':'r1','created_at':'x'},{'id':'b2','profile_code':'NEWS','briefing_date':'2026-10-06','briefing_type':'MORNING','current_published_revision_id':'r2','created_at':'x'}]
        if path.endswith('/hwarang_briefing_revisions'):
            return [{'id':'r1','briefing_id':'b1','revision_no':1,'publication_status':'published','validation_status':'ok','coverage_status':'healthy'},{'id':'r2','briefing_id':'b2','revision_no':1,'publication_status':'published','validation_status':'ok','coverage_status':'healthy'}]
        if path.endswith('/hwarang_briefing_snapshots'):
            return [{'id':'s1','revision_id':'r1','fast_brief_payload':{'core_count':1,'light_count':2},'today_action_payload':{},'qa_payload':{}},{'id':'s2','revision_id':'r2','fast_brief_payload':{'core_count':1,'light_count':2},'today_action_payload':{},'qa_payload':{}}]
        if path.endswith('/hwarang_briefing_event_updates'):
            return [{'id':'u1','event_id':'e1','change_summary':'A','observed_at':'x'},{'id':'u2','event_id':'e2','change_summary':'B','observed_at':'x'}]
        raise AssertionError(path)
def test_latest_cards_are_three_batched_metadata_reads():
    r=Repo(); assert r.latest_summaries(('NEWS',))['NEWS']; assert len(r.calls)==3
    assert all('content_payload' not in c[2].get('select','') for c in r.calls)
def test_history_is_three_batched_reads_not_n_plus_one():
    r=Repo(); assert len(r.history('NEWS'))==2; assert len(r.calls)==3
def test_timeline_is_one_batched_read():
    r=Repo(); out=r.event_updates_many(('e1','e2')); assert set(out)=={'e1','e2'}; assert len(r.calls)==1
def test_shell_has_no_user_activity_telemetry_or_artificial_sleep():
    app=(ROOT/'app.py').read_text(); all_py='\n'.join(p.read_text(errors='ignore') for p in (ROOT/'modules').rglob('*.py') if p.name!='platform_activity.py')
    assert 'log_activity(' not in app and 'hw_last_heartbeat_at' not in app and 'time.sleep(' not in all_py
def test_navigation_reuses_same_permission_list():
    app=(ROOT/'app.py').read_text(); nav=(ROOT/'modules/shell/navigation.py').read_text(); wb=(ROOT/'modules/shared/workbench.py').read_text()
    assert 'allowed=permitted' in app and 'allowed=session.get("ws_allowed_ids")' in nav and 'render_workflow(page, allowed=allowed)' in wb
