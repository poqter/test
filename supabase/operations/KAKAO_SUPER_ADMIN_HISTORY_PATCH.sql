begin;

create index kakao_admin_receipt_history_idx
on public.hwarang_admin_audit_log
    (target_user_id, (details->>'kind'), (details->>'event_id'), id desc)
where action = 'kakao_receipt_recorded';

create function private.kakao_super_admin_events(p_owner_id uuid)
returns table(
    kind text, event_id uuid, day date, reference_at timestamptz, accepted_at timestamptz,
    status text, outcome text, generation bigint, accepted_parts bigint, total_parts bigint
)
language sql stable set search_path = '' as $$
    select case when b.outcome = 'welcome_day_reserved' then 'welcome' else 'regular' end,
        b.id, b.day,
        -- Regular reservations store scheduled time plus the ten-minute window.
        case when b.outcome = 'welcome_day_reserved' then coalesce(w.ready_at, b.created_at)
             else b.delivery_deadline - interval '10 minutes' end,
        j.accepted_at,
        case when b.outcome = 'welcome_day_reserved' then
             coalesce(w.status, case when j.accepted_parts > 0 then 'accepted' else b.status end)
             else b.status end,
        case when b.outcome is distinct from 'welcome_day_reserved' then b.outcome end,
        b.generation, j.accepted_parts, j.total_parts
    from public.kakao_multi_batches b
    left join public.kakao_multi_welcomes w on w.owner_id = b.owner_id and w.batch_id = b.id
    cross join lateral (
        select max(j.completed_at) filter (where j.status = 'accepted') accepted_at,
            count(*) filter (where j.status = 'accepted') accepted_parts, count(*) total_parts
        from public.kakao_multi_jobs j where j.batch_id = b.id
    ) j
    where b.owner_id = p_owner_id

    union all

    select 'test', t.id, (t.created_at at time zone 'Asia/Seoul')::date, t.created_at,
        case when t.status = 'accepted' then t.completed_at end,
        case when t.status = 'queued' and t.expires_at <= now() then 'expired'
             when t.status = 'processing' and t.expires_at <= now() then 'uncertain'
             else t.status end,
        null, t.generation, case when t.status = 'accepted' then 1 else 0 end, 1
    from public.kakao_multi_test_requests t where t.owner_id = p_owner_id
$$;

create function private.kakao_super_admin_history(p_owner_id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
    current_generation bigint;
    today date := (now() at time zone 'Asia/Seoul')::date;
begin
    perform private.kakao_require_super_admin();
    select generation into current_generation from public.kakao_multi_connections where owner_id = p_owner_id;
    return (
        with events as (
            select e.*, row_number() over (
                partition by kind order by day desc, reference_at desc nulls last, event_id desc
            ) as kind_rank
            from private.kakao_super_admin_events(p_owner_id) e
        )
        select coalesce(jsonb_agg(
            to_jsonb(e) || jsonb_build_object(
                'in_recent_period', e.day between today - 6 and today,
                'current_connection', e.generation = current_generation,
                'request_actor', case when e.kind = 'test' then coalesce(requester.display_name, '관리자 요청 기록 없음') end,
                'receipt', receipt.details->>'receipt',
                'receipt_actor', verifier.display_name,
                'receipt_at', receipt.created_at
            ) order by e.day desc, e.reference_at desc nulls last, e.event_id desc
        ), '[]'::jsonb)
        from events e
        left join lateral (
            select actor_user_id, details, created_at
            from public.hwarang_admin_audit_log
            where target_user_id = p_owner_id and action = 'kakao_receipt_recorded'
                and details->>'kind' = e.kind and details->>'event_id' = e.event_id::text
            order by id desc limit 1
        ) receipt on true
        left join public.profiles verifier on verifier.id = receipt.actor_user_id
        left join lateral (
            select actor_user_id from public.hwarang_admin_audit_log
            where e.kind = 'test' and target_user_id = p_owner_id and action = 'kakao_test_requested'
                and details->>'request_id' = e.event_id::text
            order by id desc limit 1
        ) request_log on true
        left join public.profiles requester on requester.id = request_log.actor_user_id
        where e.day between today - 6 and today or (e.kind in ('regular', 'test') and e.kind_rank = 1)
    );
end;
$$;

create function private.kakao_super_admin_record_receipt(
    p_owner_id uuid, p_kind text, p_event_id uuid, p_receipt text
) returns boolean language plpgsql security definer set search_path = '' as $$
declare
    actor uuid := private.kakao_require_super_admin();
begin
    if p_receipt is null or p_receipt not in ('delivered','reported_missing','unconfirmed')
        or not exists (
            select 1 from private.kakao_super_admin_events(p_owner_id) e
            where e.event_id = p_event_id and e.kind = p_kind
                and (e.accepted_parts > 0 or e.status = 'uncertain' or e.outcome = 'outcome_uncertain')
        ) then
        raise exception 'Invalid receipt event' using errcode = '22023';
    end if;
    insert into public.hwarang_admin_audit_log(actor_user_id, target_user_id, action, details)
    values (actor, p_owner_id, 'kakao_receipt_recorded',
        jsonb_build_object('kind', p_kind, 'event_id', p_event_id, 'receipt', p_receipt));
    return true;
end;
$$;

create function public.kakao_super_admin_history(p_owner_id uuid) returns jsonb
language sql stable security invoker set search_path = '' as $$
    select private.kakao_super_admin_history(p_owner_id)
$$;
create function public.kakao_super_admin_record_receipt(
    p_owner_id uuid, p_kind text, p_event_id uuid, p_receipt text
) returns boolean language sql security invoker set search_path = '' as $$
    select private.kakao_super_admin_record_receipt(p_owner_id, p_kind, p_event_id, p_receipt)
$$;

revoke all on function private.kakao_super_admin_events(uuid) from public, anon, authenticated;
revoke all on function private.kakao_super_admin_history(uuid), public.kakao_super_admin_history(uuid),
    private.kakao_super_admin_record_receipt(uuid,text,uuid,text),
    public.kakao_super_admin_record_receipt(uuid,text,uuid,text) from public, anon, authenticated;
grant execute on function private.kakao_super_admin_history(uuid), public.kakao_super_admin_history(uuid),
    private.kakao_super_admin_record_receipt(uuid,text,uuid,text),
    public.kakao_super_admin_record_receipt(uuid,text,uuid,text) to authenticated;

commit;
