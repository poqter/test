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


def generate_group(repo, day, group, retry=False, actor=None, allow_partial_market=False):
    if group not in GROUPS:raise ValueError('Unknown briefing group')
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
            trigger_type='retry' if retry else 'scheduled',actor_user_id=actor,
            allow_partial_market=allow_partial_market)
        repo.save_run(key,owner,saved,'completed')
        return {'status':'completed','profiles':[r.profile_code for r in result.profiles],
                'market_news_only':bool(saved.get('market_news_only'))}
    except Exception:
        repo.save_run(key,owner,saved,'blocked' if saved.get('pending_request') or saved.get('charge_uncertain') else 'failed')
        raise


def publish_ready(repo, day, codes, *, now=None):
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
        if (now or datetime.now(timezone.utc))<publish_at:results.append({'profile':code,'status':'before_publication_time'});continue
        if revision.get('publication_status')=='published':
            results.append({'profile':code,'status':'already_published'});continue
        if revision.get('publication_status')=='hidden':
            results.append({'profile':code,'status':'hidden'});continue
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
        # Organization approval authorizes the next quality-approved edition.
        # Legacy shadow remains a storage mode, not an observation-day gate.
        if profile.get('run_mode') not in {'shadow', 'auto'}:
            results.append({'profile':code,'status':'manual_mode'});continue
        repo.publish_revision(bundle['briefing']['id'],revision['id'])
        results.append({'profile':code,'status':'published'})
    return results


def catch_up(repo, now=None):
    """Reconcile only today's due work; repeated ticks never reset paid state.

    The database claim remains the atomic authority across UI/Actions callers.
    One retry is permitted after 08:10, with the existing two-attempt cap.
    Unknown paid responses and hidden/quality-held editions are never bypassed.
    """
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('Scheduler time must include a timezone')
    day = instant.astimezone(KST).date()
    profiles = {p['profile_code']: p for p in repo.profiles()}
    def clock():
        return now or datetime.now(timezone.utc)

    def due_profiles():
        return [code for code in ('MARKET', 'NEWS', 'INSURANCE')
                if profiles.get(code, {}).get('is_enabled') is not False
                and clock() >= datetime.combine(day, time(7,30) if code == 'MARKET' else time(8), KST)]
    from .diagnostics import failure_diagnostic

    def publish_independently():
        outcomes = []
        for code in due_profiles():
            try:
                outcomes.extend(publish_ready(repo, day, (code,), now=now))
            except Exception as exc:
                outcomes.append({'profile': code, 'status': 'failed', 'diagnostic': failure_diagnostic(exc)})
        return outcomes

    # Publish saved editions first: a slow/failed MARKET cannot hold NEWS hostage.
    publish_independently()
    generation = {}
    for group in ('DAILY', 'MARKET'):
        if clock().astimezone(KST).date() != day:
            generation[group] = {'status': 'blocked', 'reason': 'business_day_changed'}
            continue
        if clock() < cutoff(day, group):
            generation[group] = {'status': 'not_due'}
            continue
        codes = [c for c in GROUPS[group] if profiles.get(c, {}).get('is_enabled') is not False]
        if not codes:
            generation[group] = {'status': 'disabled'}
            continue
        try:
            existing = [repo.bundle_for_date(c, day, include_draft=True) for c in codes]
            if all(existing):
                generation[group] = {'status': 'reused', 'reason': 'stored_editions'}
                continue
            # Do not reconstruct a partially saved group by paying for it again.
            if any(existing):
                generation[group] = {'status': 'blocked', 'reason': 'partial_saved_editions'}
                continue
            state = repo.daily_run_status(day, group)
            status = state.get('status')
            if status in ('completed', 'blocked') or int(state.get('attempts') or 0) >= 2:
                generation[group] = {'status': 'blocked', 'reason': 'stored_run_' + str(status)}
                continue
            retry = bool(state.get('attempts'))
            if retry and clock() < datetime.combine(day, time(8,10), KST):
                generation[group] = {'status': 'retry_wait'}
                continue
            generation[group] = generate_group(repo, day, group, retry=retry,
                                                allow_partial_market=group == 'MARKET')
        except Exception as exc:
            generation[group] = {'status': 'failed', 'diagnostic': failure_diagnostic(exc)}
        # Commit each available edition without waiting for another group.
        publish_independently()
    publication = publish_independently()
    due = due_profiles()
    complete = bool(due) and all(r['status'] in ('published', 'already_published') for r in publication)
    return {'status': 'published' if complete else ('incomplete' if due else 'before_publication_time'),
            'before_9am_target_missed': bool(due and not complete and clock() >= datetime.combine(day,time(9),KST)),
            'briefing_date': str(day), 'checked_at': (now or datetime.now(timezone.utc)).isoformat(),
            'due_profiles': due, 'generation': generation, 'publication': publication}


def run_scheduled(action, now=None, repo=None):
    repo=repo or BriefingRepository()
    if action=='catch_up':return catch_up(repo, now)
    now=now or datetime.now(timezone.utc); local=now.astimezone(KST); day=local.date()
    if action=='prepare':
        repo.sync_business_calendar(day)
        policy = repo.operating_policy()
        return {'status':'prepared','ai_generation_enabled':repo.ai_generation_enabled(),
                'policy':{k:policy.get(k) for k in ('scheduled_generation_enabled','automatic_publication_enabled','external_sharing_approved')},
                'enabled':[r['profile_code'] for r in repo.profiles() if r.get('is_enabled')]}
    if action=='market':
        if now<cutoff(day,'MARKET'):raise ValueError('MARKET cutoff not reached')
        return generate_group(repo,day,'MARKET',allow_partial_market=True)
    if action=='daily':
        if now<cutoff(day,'DAILY'):raise ValueError('DAILY cutoff not reached')
        published=publish_ready(repo,day,('MARKET',))
        return {'market':published,'daily':generate_group(repo,day,'DAILY')}
    if action=='publish':return publish_ready(repo,day,('MARKET','NEWS','INSURANCE'))
    if action=='recover':
        results={}
        for group in GROUPS:
            try:results[group]=generate_group(repo,day,group,retry=True,allow_partial_market=group=='MARKET')
            except Exception as exc:
                from .diagnostics import failure_diagnostic
                results[group]={'status':'failed','diagnostic':failure_diagnostic(exc)}
        results['publication']=publish_ready(repo,day,('MARKET','NEWS','INSURANCE'))
        return results
    raise ValueError('Unknown scheduled action')
