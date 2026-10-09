"""Server-only daily orchestration; viewing and sharing never enter this module."""
from datetime import datetime, time, timezone, timedelta
import uuid
from zoneinfo import ZoneInfo
from .repository import BriefingRepository
from .runtime import generate_and_store_briefings, body_quality_ready

KST=ZoneInfo('Asia/Seoul')
GROUPS={'MARKET':('MARKET',),'DAILY':('NEWS','INSURANCE')}


def cutoff(day, group):
    return datetime.combine(day,time(7,0) if group=='MARKET' else time(7,30),KST).astimezone(timezone.utc)


def generate_group(repo, day, group, retry=False, actor=None):
    if group not in GROUPS:raise ValueError('Unknown briefing group')
    if group == 'MARKET':
        from .market_metrics import market_observations_configured
        if not market_observations_configured():
            return {'status':'configuration_required','reason':'market_observations_not_configured'}
    if actor is None and not repo.operating_policy().get('scheduled_generation_enabled'):
        return {'status':'skipped','reason':'scheduled_generation_paused'}
    if actor is not None:repo.require_manager(actor)
    if not repo.ai_generation_enabled():return {'status':'blocked','reason':'platform_ai_service_disabled'}
    repo.sync_business_calendar(day)
    owner=str(uuid.uuid4()); key=f'{day}:{group}'
    claim=repo.claim_run(key,day,group,owner,retry)
    if not claim.get('claimed'): return {'status':'skipped','reason':claim.get('status')}
    saved=claim.get('checkpoint') or {}
    def save(state):repo.save_run(key,owner,state)
    if saved.get('pending_request') or saved.get('charge_uncertain'):
        repo.save_run(key,owner,saved,'blocked'); return {'status':'blocked','reason':'unconfirmed_api_request'}
    if group=='MARKET' and not (saved.get('market_observations') or {}).get('complete'):
        from .market_metrics import collect_metrics
        saved['market_observations']=collect_metrics(cutoff(day,group));save(saved)
        if not saved['market_observations'].get('complete'):
            repo.save_run(key,owner,saved,'failed')
            return {'status':'configuration_required','reason':'market_observations_incomplete',
                    'missing':saved['market_observations'].get('missing',[])}
    def before(kind):
        if saved.get('pending_request') or saved.get('charge_uncertain'):
            raise RuntimeError('이전 유료 요청 상태를 확인할 수 없어 추가 호출을 중단합니다.')
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
    policy=repo.operating_policy()
    for code in codes:
        if profiles.get(code,{}).get('is_enabled') is False:
            results.append({'profile':code,'status':'disabled'});continue
        bundle=repo.bundle_for_date(code,day,include_draft=True)
        if not bundle:results.append({'profile':code,'status':'no_snapshot'});continue
        revision=bundle['revision']; qa=bundle['snapshot'].get('qa_payload') or {}
        publish_at=datetime.combine(day,time(7,30) if code=='MARKET' else time(8),KST)
        if datetime.now(timezone.utc)<publish_at:results.append({'profile':code,'status':'before_publication_time'});continue
        if revision.get('publication_status')=='published':continue
        if revision.get('publication_status')=='hidden':continue
        from .public_body import customer_body
        body=bundle['snapshot'].get('external_content_payload') or {}
        content=bundle['snapshot'].get('content_payload') or {}
        if content.get('issues'):body=content
        elif body.get('schema')!='hwarang-public-v2':body=customer_body(content)
        if not body_quality_ready(body):
            results.append({'profile':code,'status':'quality_hold'});continue
        if revision.get('validation_status')!='ok' or revision.get('coverage_status')!='healthy' or not qa.get('internal_body_ready'):
            results.append({'profile':code,'status':'quality_hold'});continue
        profile=profiles.get(code) or {}
        if not policy.get('automatic_publication_enabled'):
            results.append({'profile':code,'status':'organization_approval_required'});continue
        good_days=repo.verified_business_days(code)
        if profile.get('run_mode')=='shadow' and good_days>=3:
            repo._request('PATCH','/rest/v1/hwarang_briefing_profiles',params={'profile_code':'eq.'+code},json={'run_mode':'auto'})
            profile['run_mode']='auto'
        if profile.get('run_mode')=='auto':
            repo.publish_revision(bundle['briefing']['id'],revision['id']);results.append({'profile':code,'status':'published'})
        else:results.append({'profile':code,'status':'observation','verified_business_days':good_days})
    return results


def run_scheduled(action, now=None, repo=None):
    repo=repo or BriefingRepository(); now=now or datetime.now(timezone.utc); local=now.astimezone(KST); day=local.date()
    if action=='prepare':
        repo.sync_business_calendar(day)
        return {'status':'prepared','ai_generation_enabled':repo.ai_generation_enabled(),
                'policy':{k:repo.operating_policy().get(k) for k in ('scheduled_generation_enabled','automatic_publication_enabled','external_sharing_approved')},
                'enabled':[r['profile_code'] for r in repo.profiles() if r.get('is_enabled')]}
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
