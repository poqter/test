-- 25: per-user claim serialization, explicit recovery and truthful operational status.
-- Requires migrations 23 and 24. Does not automatically release existing requests.
begin;
create or replace function public.hwarang_studio_claim(p_actor uuid,p_id uuid,p_version integer,p_op text,p_purpose text)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare rec public.hwarang_studio_records; req public.hwarang_studio_requests;
begin
 perform private.studio_check(p_actor);
 -- Serialize claims for ONE user, including claims from different sessions.
 perform pg_advisory_xact_lock(hashtextextended(p_actor::text,0));
 select * into rec from public.hwarang_studio_records where id=p_id and user_id=p_actor for update;
 if not found then raise exception 'STUDIO_ACCESS_DENIED';end if;
 select * into req from public.hwarang_studio_requests where op_key=p_op;
 if found then
  if req.user_id<>p_actor or req.session_id<>p_id then raise exception 'STUDIO_ACCESS_DENIED';end if;
  return to_jsonb(req)||jsonb_build_object('fresh',false);
 end if;
 if rec.version<>p_version then raise exception 'STUDIO_VERSION_CONFLICT';end if;
 if rec.locked_by is not null or exists(select 1 from public.hwarang_studio_requests where user_id=p_actor and status in ('claimed','processing','uncertain'))
 then raise exception 'STUDIO_REQUEST_PENDING';end if;
 if p_purpose not in ('CUSTOMER','COACH','EVALUATOR','TRANSCRIBE','SPEECH') or char_length(p_op)>180 then raise exception 'INVALID_STUDIO_REQUEST';end if;
 insert into public.hwarang_studio_requests(op_key,session_id,user_id,base_version,purpose,status)
 values(p_op,p_id,p_actor,p_version,p_purpose,'claimed') returning * into req;
 update public.hwarang_studio_records set locked_by=p_op where id=p_id;
 return to_jsonb(req)||jsonb_build_object('fresh',true);
end $$;

create or replace function public.hwarang_studio_release_unknown(p_actor uuid,p_op text,p_note text)
returns void language plpgsql security invoker set search_path='' as $$
declare
 target_user uuid; target_session uuid; rec public.hwarang_studio_records;
 req public.hwarang_studio_requests; ledger public.hwarang_ai_request_registry;
 recovery_note text;
begin
 if not exists(select 1 from public.profiles where id=p_actor and role='super_admin' and is_active)
 then raise exception 'STUDIO_ACCESS_DENIED'; end if;
 if length(trim(p_note))<10 or length(p_note)>1000 then raise exception 'RECOVERY_NOTE_REQUIRED'; end if;
 recovery_note:=p_note;
 select user_id into target_user from public.hwarang_studio_requests where op_key=p_op;
 if not found then raise exception 'REQUEST_NOT_FOUND'; end if;
  perform pg_advisory_xact_lock(hashtextextended(target_user::text,0));
  select session_id into target_session from public.hwarang_studio_requests
    where op_key=p_op and user_id=target_user;
  if not found then raise exception 'STOP: exact request not found; no change'; end if;
  -- Same lock order as normal Studio save/claim.
  select * into rec from public.hwarang_studio_records
    where id=target_session and user_id=target_user for update;
  if not found then raise exception 'STOP: request session not found'; end if;
  select * into req from public.hwarang_studio_requests
    where op_key=p_op and user_id=target_user for update;
  if exists(select 1 from public.hwarang_studio_audit
    where session_id=target_session and event='authorized_unknown_release'
      and detail->>'op_key'=p_op) then
    raise notice 'Already released by this script; no further changes';
    return;
  end if;
  if req.status not in ('claimed','processing','uncertain')
      or req.updated_at>now()-interval '10 minutes' then
    raise exception 'STOP: request state/age changed; review before recovery';
  end if;
  if rec.locked_by is not null and rec.locked_by<>p_op then
    raise exception 'STOP: session has a different lock';
  end if;
  if req.request_id is null then
    -- Reservation may have committed before the transport reply was lost.
    select request_id into req.request_id from public.hwarang_ai_request_registry
      where idempotency_key=p_op and user_id=target_user and academy_session_id=target_session;
    if req.request_id is null and req.status<>'claimed' then raise exception 'STOP: credit reference missing'; end if;
  end if;
  if req.request_id is not null then
  select * into ledger from public.hwarang_ai_request_registry
    where request_id=req.request_id for update;
  if not found or ledger.user_id<>target_user
      or ledger.academy_session_id is distinct from target_session then
    raise exception 'STOP: credit ledger identity mismatch';
  end if;
  -- Release only an outstanding learner-credit reservation using the existing
  -- bucket-aware function. This does NOT assert that the provider charged zero.
  -- Already completed/expired/failed ledgers and prior consumed credits stay intact.
  if ledger.status in ('reserved','processing') then
    if req.purpose in ('TRANSCRIBE','SPEECH') then
      perform public.finalize_hwarang_voice_request(ledger.request_id,'failed',0);
    else
      perform public.finalize_hwarang_ai_request(ledger.request_id,'failed',0);
    end if;
  elsif ledger.status not in ('completed','expired','failed','blocked') then
    raise exception 'STOP: unexpected credit ledger state';
  end if;
  update public.hwarang_ai_request_registry
    set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'studio_recovery','authorized_unknown_release',
      'provider_processing_status','unknown','provider_cost_status','unknown',
      'recovery_note',recovery_note,'recovered_at',now())
    where request_id=ledger.request_id;
  end if;
  update public.hwarang_studio_requests
    set status='failed',updated_at=now(),request_id=req.request_id,
      result=coalesce(result,'{}'::jsonb)||jsonb_build_object('recovery',jsonb_build_object(
        'kind','authorized_unknown_release','provider_processing_status','unknown',
        'provider_cost_status','unknown','note',recovery_note))
    where op_key=p_op;
  update public.hwarang_studio_records
    set locked_by=null,version=version+1,
      data=jsonb_set(data,'{version}',to_jsonb(version+1)),updated_at=now()
    where id=target_session;
  perform public.release_hwarang_ai_session(target_user,target_session);
  insert into public.hwarang_studio_audit(actor,session_id,event,detail)
    values(p_actor,target_session,'authorized_unknown_release',jsonb_build_object(
      'op_key',p_op,'request_id',req.request_id,
      'previous_studio_status',req.status,'previous_ledger_status',ledger.status,
      'previous_record_version',rec.version,'provider_processing_status','unknown',
      'provider_cost_status','unknown','provider_recalled',false,'note',recovery_note));
end $$;
create or replace function public.hwarang_studio_operations(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 if not exists(select 1 from public.profiles where id=p_actor and role='super_admin' and is_active)
 then raise exception 'STUDIO_ACCESS_DENIED'; end if;
 return jsonb_build_object(
 'pending',(select count(*) from public.hwarang_studio_requests where status in ('claimed','processing','uncertain')),
 'affected_users',(select count(distinct user_id) from public.hwarang_studio_requests where status in ('claimed','processing','uncertain')),
 'oldest_pending',(select min(created_at) from public.hwarang_studio_requests where status in ('claimed','processing','uncertain')),
 'unknown_cost',(select count(*) from public.hwarang_ai_usage_log where calculated_cost_usd is null or cost_status='unknown'),
 'recovered_unknown',(select count(*) from public.hwarang_studio_requests where result->'recovery'->>'provider_cost_status'='unknown'),
 'failed_24h',(select count(*) from public.hwarang_studio_requests where status='failed' and updated_at>now()-interval '24 hours'));
end $$;
create or replace function public.hwarang_studio_my_pending(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 perform private.studio_check(p_actor);
 return coalesce((select jsonb_agg(jsonb_build_object('op_key',op_key,'purpose',purpose,'status',status,'created_at',created_at,'updated_at',updated_at))
 from public.hwarang_studio_requests where user_id=p_actor and status in ('claimed','processing','uncertain')),'[]');
end $$;
revoke all on function public.hwarang_studio_release_unknown(uuid,text,text),public.hwarang_studio_operations(uuid),public.hwarang_studio_my_pending(uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_release_unknown(uuid,text,text),public.hwarang_studio_operations(uuid),public.hwarang_studio_my_pending(uuid) to service_role;
commit;
