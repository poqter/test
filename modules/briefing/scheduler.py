"""Server-only daily orchestration; viewing and sharing never enter this module."""
from datetime import datetime, time, timezone, timedelta
import uuid
from zoneinfo import ZoneInfo
from .repository import BriefingRepository
from .runtime import generate_and_store_briefings

KST=ZoneInfo('Asia/Seoul')
GROUPS={'MARKET':('MARKET',),'DAILY':('NEWS','INSURANCE')}


def cutoff(day, group):
    return datetime.combine(day,time(7,0) if group=='MARKET' else time(7,30),KST).astimezone(timezone.utc)


def generate_group(repo, day, group, retry=False, actor=None):
    owner=str(uuid.uuid4()); key=f'{day}:{group}'
    claim=repo.claim_run(key,day,group,owner,retry)
    if not claim.get('claimed'): return {'status':'skipped','reason':claim.get('status')}
    saved=claim.get('checkpoint') or {}
    def save(state):repo.save_run(key,owner,state)
    if saved.get('pending_request') or saved.get('charge_uncertain'):
        repo.save_run(key,owner,saved,'blocked'); return {'status':'blocked','reason':'unconfirmed_api_request'}
    def before(kind):
        saved['pending_request']={'kind':kind,'at':datetime.now(timezone.utc).isoformat()};save(saved)
        try:repo.reserve_request(day,kind)
        except Exception:
            saved.pop('pending_request',None);save(saved);raise
    try:
        repo.finish_stale_jobs(day,GROUPS[group])
        result=generate_and_store_briefings(repository=repo,profile_codes=GROUPS[group],force_shadow=True,
            as_of=cutoff(day,group),checkpoint=saved,save_checkpoint=save,before_request=before,
            trigger_type='retry' if retry else 'scheduled',actor_user_id=actor)
        repo.save_run(key,owner,saved,'completed')
        return {'status':'completed','profiles':[r.profile_code for r in result.profiles]}
    except Exception:
        repo.save_run(key,owner,saved,'blocked' if saved.get('pending_request') or saved.get('charge_uncertain') else 'failed')
        raise


def publish_ready(repo, day, codes):
    results=[]
    profiles={r['profile_code']:r for r in repo.profiles()}
    for code in codes:
        bundle=repo.bundle_for_date(code,day,include_draft=True)
        if not bundle:results.append({'profile':code,'status':'no_snapshot'});continue
        revision=bundle['revision']; qa=bundle['snapshot'].get('qa_payload') or {}
        if revision.get('publication_status')=='published':continue
        if revision.get('publication_status')=='hidden':continue
        if revision.get('validation_status')!='ok' or revision.get('coverage_status')!='healthy' or not qa.get('public_body_ready'):
            results.append({'profile':code,'status':'quality_hold'});continue
        profile=profiles.get(code) or {}
        # One normal workweek of observation is automatic, without a daily approval ritual.
        good_days=set()
        for item in repo.history(code,limit=30,include_draft=True):
            from datetime import date
            try:d=date.fromisoformat(item['briefing']['briefing_date'])
            except (ValueError,KeyError):continue
            rev=item['revision']; q=item['snapshot'].get('qa_payload') or {}
            if d.weekday()<5 and day-timedelta(days=30)<=d<=day and rev.get('validation_status')=='ok' and rev.get('coverage_status')=='healthy' and q.get('public_body_ready'):
                good_days.add(d)
        if profile.get('run_mode')=='shadow' and len(good_days)>=3:
            repo._request('PATCH','/rest/v1/hwarang_briefing_profiles',params={'profile_code':'eq.'+code},json={'run_mode':'auto'})
            profile['run_mode']='auto'
        if profile.get('run_mode')=='auto':
            repo.publish_revision(bundle['briefing']['id'],revision['id']);results.append({'profile':code,'status':'published'})
        else:results.append({'profile':code,'status':'observation','verified_business_days':len(good_days)})
    return results


def run_scheduled(action, now=None, repo=None):
    repo=repo or BriefingRepository(); now=now or datetime.now(timezone.utc); local=now.astimezone(KST); day=local.date()
    if action=='prepare':return {'status':'prepared','enabled':[r['profile_code'] for r in repo.profiles() if r.get('is_enabled')]}
    if action=='market':
        if now<cutoff(day,'MARKET'):raise ValueError('MARKET cutoff not reached')
        return generate_group(repo,day,'MARKET')
    if action=='daily':
        if now<cutoff(day,'DAILY'):raise ValueError('DAILY cutoff not reached')
        published=publish_ready(repo,day,('MARKET',))
        return {'market':published,'daily':generate_group(repo,day,'DAILY')}
    if action=='publish':return publish_ready(repo,day,('MARKET','NEWS','INSURANCE'))
    if action=='recover':
        results={}
        for group in GROUPS:
            try:results[group]=generate_group(repo,day,group,retry=True)
            except Exception:results[group]={'status':'failed','message':'See protected operation log'}
        results['publication']=publish_ready(repo,day,('MARKET','NEWS','INSURANCE'))
        return results
    raise ValueError('Unknown scheduled action')
