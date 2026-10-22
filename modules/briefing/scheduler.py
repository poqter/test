"""Server-only daily orchestration; viewing and sharing never enter this module."""
from datetime import datetime, time, timezone, timedelta
import uuid
from zoneinfo import ZoneInfo
from .repository import BriefingRepository
from .runtime import generate_and_store_briefings, body_quality_ready

KST=ZoneInfo('Asia/Seoul')
GROUPS={'MARKET':('MARKET',),'NEWS':('NEWS',),'INSURANCE':('INSURANCE',)}


def cutoff(day, group):
    return datetime.combine(day,time(7,30),KST).astimezone(timezone.utc)


def collect_early(repo, day, slot):
    """Two free, durable candidate collections; never a final editorial selection."""
    if not repo.operating_policy().get('scheduled_generation_enabled'):
        return {'status':'skipped','reason':'scheduled_generation_paused'}
    key=f'{day}:COLLECT_{slot}'; owner=str(uuid.uuid4())
    claim=repo.claim_run(key,day,'COLLECT',owner,False)
    if not claim.get('claimed'): return {'status':'reused'}
    saved=claim.get('checkpoint') or {}
    try:
        from .phase_b import run_phase_b
        from .direct_sources import load_direct_source_specs_from_env
        from .checkpoints import encode
        from .publication import PublicationDateEnricher
        result=run_phase_b(as_of=datetime.now(timezone.utc), date_enricher=PublicationDateEnricher(max_requests=0),
            direct_sources=load_direct_source_specs_from_env(), enable_web_discovery=False)
        saved['early_collection']=encode(result)
        repo.save_run(key,owner,saved,'completed')
        return {'status':'collected','candidates':len(result.candidates),'paid_requests':0}
    except Exception:
        repo.save_run(key,owner,saved,'failed')
        raise


def generate_group(repo, day, group, retry=False, actor=None, allow_partial_market=False, now=None):
    if group not in GROUPS and group != 'DAILY':raise ValueError('Unknown briefing group')
    if actor is None and not repo.operating_policy().get('scheduled_generation_enabled'):
        return {'status':'skipped','reason':'scheduled_generation_paused'}
    if actor is not None:repo.require_manager(actor)
    if not repo.ai_generation_enabled():return {'status':'blocked','reason':'platform_ai_service_disabled'}
    if group == 'DAILY':
        results={}
        for code in ('NEWS','INSURANCE'):
            try: results[code]=generate_group(repo,day,code,retry,actor,now=now)
            except Exception as exc:
                from .diagnostics import failure_diagnostic
                results[code]={'status':'failed','diagnostic':failure_diagnostic(exc)}
        return results
    if group in ('NEWS','INSURANCE'):
        legacy=repo.daily_run_status(day,'DAILY')
        if isinstance(legacy,dict) and legacy.get('attempts'):
            return {'status':'blocked','reason':'legacy_daily_run_preserved'}
    repo.sync_business_calendar(day)
    owner=str(uuid.uuid4()); key=f'{day}:{group}'
    claim=repo.claim_run(key,day,group,owner,retry)
    if not claim.get('claimed'): return {'status':'skipped','reason':claim.get('status')}
    saved=claim.get('checkpoint') or {}
    if not saved.get('phase_b') and not saved.get('seed_candidates'):
        candidates=[]
        for slot in ('630','720'):
            state=repo.daily_run_status(day,'COLLECT_'+slot)
            early=state.get('checkpoint',{}).get('early_collection',{}) if isinstance(state,dict) else {}
            candidates.extend(early.get('candidates',[]))
        saved['seed_candidates']=candidates
    def save(state):repo.save_run(key,owner,state)
    if saved.get('pending_request') or saved.get('charge_uncertain'):
        repo.save_run(key,owner,saved,'blocked'); return {'status':'blocked','reason':'unconfirmed_api_request'}
    def before(kind):
        local=(now or datetime.now(KST)).astimezone(KST)
        if actor is None and (local.date()!=day or local.time()>=time(8,50)
                or kind != 'analysis' and local.time()>=time(8,40)):
            raise RuntimeError('자동 운영 신규 요청 마감: 저장 결과만 사용합니다.')
        if retry and saved.get('supplement_started'):
            raise RuntimeError('추가 분석 기회를 사용해 신규 유료 재시도를 중단합니다.')
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
            allow_partial_market=allow_partial_market,
            saved_material_only=actor is None and (now or datetime.now(KST)).astimezone(KST).time()>=time(8,40))
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
        publish_at=datetime.combine(day,time(8),KST)
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
                and clock() >= datetime.combine(day, time(8), KST)]
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
    local=clock().astimezone(KST)
    if time(6,30)<=local.time()<time(7,30):
        slot='720' if local.time()>=time(7,20) else '630'
        try:generation['collection']=collect_early(repo,day,slot)
        except Exception as exc:generation['collection']={'status':'failed','diagnostic':failure_diagnostic(exc)}
    for group in ('NEWS', 'INSURANCE', 'MARKET'):
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
            if clock()>=datetime.combine(day,time(8,50),KST):
                generation[group]={'status':'blocked','reason':'new_generation_deadline'}
                continue
            # Do not evade a pre-upgrade DAILY paid-request lock with new keys.
            legacy=repo.daily_run_status(day,'DAILY') if group in ('NEWS','INSURANCE') else {}
            if legacy.get('attempts'):
                generation[group]={'status':'blocked','reason':'legacy_daily_run_preserved'}
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
                                                allow_partial_market=group == 'MARKET', now=now)
        except Exception as exc:
            generation[group] = {'status': 'failed', 'diagnostic': failure_diagnostic(exc)}
        # Commit each available edition without waiting for another group.
        publish_independently()
    publication = publish_independently()
    due = due_profiles()
    complete = bool(due) and all(r['status'] in ('published', 'already_published') for r in publication)
    notification_required = False
    notification = 'none'
    failures = [r for r in publication if r.get('status') == 'failed']
    failures += [r for r in generation.values() if r.get('status') == 'failed']
    final_missed = bool(due and not complete and clock() >= datetime.combine(day,time(9),KST))
    if failures or final_missed:
        notification = 'final_unpublished' if final_missed else 'system_error'
        # Atomic daily claim deduplicates workflow failure notifications across
        # scheduled and watchdog callers. It never reserves an AI request.
        if hasattr(repo, 'claim_run'):
            alert_key=f'{day}:ALERT_{notification}'
            alert_owner=str(uuid.uuid4())
            alert=repo.claim_run(alert_key,day,'ALERT_'+notification,alert_owner,False)
            notification_required=bool(alert.get('claimed'))
            if notification_required:
                repo.save_run(alert_key,alert_owner,{'notification':notification,'publication':publication},'completed')
    return {'notification_required':notification_required,'notification':notification,
            'status': 'published' if complete else ('incomplete' if due else 'before_publication_time'),
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
