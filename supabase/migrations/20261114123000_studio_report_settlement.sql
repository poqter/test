-- Save feedback and settle its reservation in one transaction.
create or replace function public.hwarang_studio_settle_report(p_actor uuid, p_data jsonb, p_op text, p_failure_reason text)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare
    rec public.hwarang_studio_records;
    req public.hwarang_studio_requests;
    ledger public.hwarang_ai_request_registry;
    envelope jsonb;
    saved jsonb;
    credits bigint;
    settled_at timestamptz;
begin
    perform private.studio_check(p_actor);
    if p_failure_reason is not null and p_failure_reason not in (
        'duplicate_criterion', 'criterion_set_mismatch', 'invalid_evidence_turn',
        'evidence_quote_mismatch', 'missing_evidence'
    ) then raise exception 'INVALID_REPORT_FAILURE_REASON'; end if;

    perform pg_advisory_xact_lock(hashtextextended(p_actor::text, 0));
    select * into rec from public.hwarang_studio_records
      where id=(p_data->>'id')::uuid and user_id=p_actor for update;
    if not found then raise exception 'STUDIO_ACCESS_DENIED'; end if;
    select * into req from public.hwarang_studio_requests
      where op_key=p_op and session_id=rec.id and user_id=p_actor for update;
    if not found or req.purpose not in ('EVALUATOR','COACH')
        or req.status not in ('received','completed') or req.request_id is null
        or not coalesce((rec.data->>'ended')::boolean and (p_data->>'ended')::boolean,false)
        or jsonb_typeof(p_data->'report') is distinct from 'object'
        or req.base_version is distinct from (p_data->>'version')::integer
        or (p_failure_reason is not null) is distinct from
           coalesce(p_data->'report'->>'status'='평가 근거 확인 필요',false)
    then raise exception 'INVALID_STUDIO_REPORT_SETTLEMENT'; end if;

    if rec.version=req.base_version+1 and req.status='completed'
        and rec.data->'report'=p_data->'report' then return rec.data; end if;
    if rec.version<>req.base_version or rec.locked_by is distinct from p_op then
        raise exception 'STUDIO_VERSION_CONFLICT';
    end if;

    select * into ledger from public.hwarang_ai_request_registry
      where request_id=req.request_id and user_id=p_actor and academy_session_id=rec.id
        and purpose=req.purpose for update;
    if not found then raise exception 'INVALID_STUDIO_REPORT_SETTLEMENT'; end if;

    envelope := req.result;
    if req.status='received' and ledger.status in ('reserved','processing') then
        perform public.finalize_hwarang_ai_request(
            req.request_id,
            case when p_failure_reason is null then 'completed' else 'failed' end,
            case when p_failure_reason is null then (envelope->>'credits')::bigint else 0 end
        );
        select * into ledger from public.hwarang_ai_request_registry where request_id=req.request_id;
    end if;
    if ledger.status not in ('completed','failed','expired') then
        raise exception 'INVALID_STUDIO_REPORT_SETTLEMENT';
    end if;

    credits := coalesce(ledger.actual_credits,0);
    settled_at := now();
    envelope := envelope || jsonb_build_object('credits',credits);
    if p_failure_reason is not null then
        envelope := envelope || jsonb_build_object('report_validation',jsonb_build_object(
            'reason',p_failure_reason,'recorded_at',settled_at,'credit_status',ledger.status));
    end if;
    perform public.hwarang_studio_request_update(p_actor,p_op,'completed',req.request_id,envelope);

    saved := jsonb_set(p_data,'{usage}',coalesce(rec.data->'usage','[]'::jsonb) ||
      jsonb_build_array(envelope-'result'-'audio'-'report_validation'));
    return public.hwarang_studio_store(p_actor,saved,req.base_version,p_op);
end $$;

revoke all on function public.hwarang_studio_settle_report(uuid,jsonb,text,text) from public,anon,authenticated;
grant execute on function public.hwarang_studio_settle_report(uuid,jsonb,text,text) to service_role;

create or replace function public.hwarang_studio_report_incidents(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
    if not exists(select 1 from public.profiles where id=p_actor and role='super_admin' and is_active)
    then raise exception 'STUDIO_ACCESS_DENIED'; end if;
    return coalesce((
        select jsonb_agg(to_jsonb(incident) order by incident.recorded_at desc)
        from (
            select r.session_id, r.purpose,
                   r.result->'report_validation'->>'reason' as reason,
                   (r.result->'report_validation'->>'recorded_at')::timestamptz as recorded_at,
                   r.result->'report_validation'->>'credit_status' as credit_status,
                   u.credits_charged, u.cost_status
            from public.hwarang_studio_requests r
            left join public.hwarang_ai_usage_log u on u.request_id=r.request_id
            where r.purpose in ('EVALUATOR','COACH') and r.result ? 'report_validation'
              and r.updated_at >= now()-interval '7 days'
            order by recorded_at desc limit 30
        ) incident
    ),'[]'::jsonb);
end $$;

revoke all on function public.hwarang_studio_report_incidents(uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_report_incidents(uuid) to service_role;
