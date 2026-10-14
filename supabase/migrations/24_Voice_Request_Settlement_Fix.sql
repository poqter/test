-- 24: Correct existing Voice settlement column/output-variable ambiguity.
-- Apply after 23. No account balances or historical ledgers are rewritten.
begin;
create or replace function public.finalize_hwarang_voice_request(
    p_request_id uuid,
    p_result_status text,
    p_actual_seconds bigint
)
returns table(
    balance_seconds bigint,
    reserved_seconds bigint,
    available_seconds bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_request public.hwarang_ai_request_registry%rowtype;
    v_account public.hwarang_voice_accounts%rowtype;
    v_other_reserved bigint;
begin
    if p_result_status not in ('completed','failed') then
        raise exception 'INVALID_AI_RESULT_STATUS';
    end if;

    if p_actual_seconds < 0 then
        raise exception 'INVALID_VOICE_SECONDS';
    end if;

    select *
    into v_request
    from public.hwarang_ai_request_registry
    where request_id = p_request_id
    for update;

    if not found then
        raise exception 'AI_REQUEST_NOT_FOUND';
    end if;

    if v_request.billing_bucket <> 'VOICE' then
        raise exception 'AI_REQUEST_NOT_VOICE';
    end if;

    if v_request.status in ('completed','failed','expired') then
        select
            a.balance_seconds,
            a.reserved_seconds,
            greatest(0, a.balance_seconds - a.reserved_seconds)
        into balance_seconds, reserved_seconds, available_seconds
        from public.hwarang_voice_accounts a
        where a.user_id = v_request.user_id;

        return next;
        return;
    end if;

    if p_actual_seconds > v_request.reserved_voice_seconds then
        raise exception 'VOICE_USAGE_EXCEEDS_RESERVATION';
    end if;

    select *
    into v_account
    from public.hwarang_voice_accounts
    where user_id = v_request.user_id
    for update;

    v_other_reserved := greatest(
        0,
        v_account.reserved_seconds - v_request.reserved_voice_seconds
    );

    if p_result_status = 'completed' then
        update public.hwarang_voice_accounts as a
        set balance_seconds = a.balance_seconds - p_actual_seconds,
            reserved_seconds = v_other_reserved,
            updated_at = now()
        where user_id = v_request.user_id
        returning a.* into v_account;

        if p_actual_seconds > 0 then
            insert into public.hwarang_voice_ledger(
                user_id,
                entry_type,
                delta_seconds,
                balance_after_seconds,
                allocation_after_seconds,
                request_id,
                note
            )
            values (
                v_request.user_id,
                'consume',
                -p_actual_seconds,
                v_account.balance_seconds,
                v_account.allocation_seconds,
                v_request.request_id,
                'Voice training usage'
            );
        end if;

        update public.hwarang_ai_request_registry
        set status = 'completed',
            actual_voice_seconds = p_actual_seconds,
            completed_at = now()
        where request_id = p_request_id;

    else
        update public.hwarang_voice_accounts as a
        set reserved_seconds = v_other_reserved,
            updated_at = now()
        where user_id = v_request.user_id
        returning a.* into v_account;

        update public.hwarang_ai_request_registry
        set status = 'failed',
            actual_voice_seconds = 0,
            completed_at = now()
        where request_id = p_request_id;
    end if;

    balance_seconds := v_account.balance_seconds;
    reserved_seconds := v_account.reserved_seconds;
    available_seconds := greatest(
        0,
        v_account.balance_seconds - v_account.reserved_seconds
    );

    return next;
end;
$$;

revoke all on function public.finalize_hwarang_voice_request(uuid,text,bigint) from public,anon,authenticated;
grant execute on function public.finalize_hwarang_voice_request(uuid,text,bigint) to service_role;
notify pgrst,'reload schema';
commit;
