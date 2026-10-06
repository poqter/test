-- =========================================================
-- HWARANG PLATFORM
-- 15 ADMIN CENTER V2 VOICE AMBIGUITY FIX v1
--
-- Apply ONCE after 14_Admin_Center_V2_Asset_Adjustments.sql.
-- Fixes PostgreSQL PL/pgSQL ambiguity between RETURNS TABLE
-- output variables (allocation_seconds / balance_seconds) and
-- hwarang_voice_accounts columns.
-- No data reset or balance rewrite is performed.
-- =========================================================

begin;

create or replace function public.admin_adjust_hwarang_voice_minutes(
    p_actor_user_id uuid,
    p_target_user_id uuid,
    p_operation text,
    p_minutes bigint,
    p_source_type text,
    p_note text
)
returns table(
    allocation_seconds bigint,
    balance_seconds bigint,
    reserved_seconds bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_account public.hwarang_voice_accounts%rowtype;
    v_seconds bigint;
    v_delta bigint;
    v_source text;
begin
    if not exists (
        select 1
        from public.profiles
        where id = p_actor_user_id
          and role = 'super_admin'
          and is_active = true
    ) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;

    if not exists (
        select 1
        from public.profiles
        where id = p_target_user_id
    ) then
        raise exception 'TARGET_USER_NOT_FOUND';
    end if;

    if p_operation not in ('grant','revoke','reset') then
        raise exception 'INVALID_VOICE_OPERATION';
    end if;

    if p_operation in ('grant','revoke') and p_minutes <= 0 then
        raise exception 'INVALID_VOICE_MINUTES';
    end if;

    if p_operation = 'reset' and p_minutes < 0 then
        raise exception 'INVALID_VOICE_MINUTES';
    end if;

    v_source := lower(coalesce(nullif(btrim(p_source_type),''),'admin_adjustment'));
    if v_source = 'bonus' then
        v_source := 'promotion_reward';
    end if;

    if v_source not in ('purchase','promotion_reward','admin_adjustment','migration','system') then
        raise exception 'INVALID_VOICE_SOURCE';
    end if;

    v_seconds := p_minutes * 60;

    insert into public.hwarang_voice_accounts(user_id)
    values (p_target_user_id)
    on conflict (user_id) do nothing;

    select *
    into v_account
    from public.hwarang_voice_accounts
    where user_id = p_target_user_id
    for update;

    if v_account.reserved_seconds > 0
       and p_operation in ('revoke','reset') then
        raise exception 'VOICE_ACTIVE_RESERVATION';
    end if;

    if p_operation = 'grant' then
        v_delta := v_seconds;

        update public.hwarang_voice_accounts va
        set allocation_seconds = va.allocation_seconds + v_seconds,
            balance_seconds = va.balance_seconds + v_seconds,
            updated_at = now()
        where va.user_id = p_target_user_id
        returning * into v_account;

    elsif p_operation = 'revoke' then
        if v_seconds > greatest(0::bigint, v_account.balance_seconds - v_account.reserved_seconds) then
            raise exception 'VOICE_REVOKE_EXCEEDS_AVAILABLE';
        end if;

        v_delta := -v_seconds;

        update public.hwarang_voice_accounts va
        set allocation_seconds = greatest(0::bigint, va.allocation_seconds - v_seconds),
            balance_seconds = va.balance_seconds - v_seconds,
            updated_at = now()
        where va.user_id = p_target_user_id
        returning * into v_account;

    else
        v_delta := v_seconds - v_account.balance_seconds;

        update public.hwarang_voice_accounts va
        set allocation_seconds = v_seconds,
            balance_seconds = v_seconds,
            reserved_seconds = 0,
            updated_at = now()
        where va.user_id = p_target_user_id
        returning * into v_account;
    end if;

    insert into public.hwarang_voice_ledger(
        user_id,
        entry_type,
        delta_seconds,
        balance_after_seconds,
        allocation_after_seconds,
        request_id,
        actor_user_id,
        note,
        source_type
    )
    values (
        p_target_user_id,
        p_operation,
        v_delta,
        v_account.balance_seconds,
        v_account.allocation_seconds,
        null,
        p_actor_user_id,
        nullif(btrim(coalesce(p_note,'')),''),
        v_source
    );

    insert into public.hwarang_admin_audit_log(
        actor_user_id,
        target_user_id,
        action,
        details
    )
    values (
        p_actor_user_id,
        p_target_user_id,
        'voice_minutes_' || p_operation,
        jsonb_build_object(
            'minutes', p_minutes,
            'delta_seconds', v_delta,
            'source_type', v_source,
            'balance_after_seconds', v_account.balance_seconds,
            'allocation_after_seconds', v_account.allocation_seconds,
            'note', p_note
        )
    );

    return query
    select
        v_account.allocation_seconds,
        v_account.balance_seconds,
        v_account.reserved_seconds;
end;
$$;

revoke all on function public.admin_adjust_hwarang_voice_minutes(uuid,uuid,text,bigint,text,text)
from public, anon, authenticated;
grant execute on function public.admin_adjust_hwarang_voice_minutes(uuid,uuid,text,bigint,text,text)
to service_role;

commit;

notify pgrst, 'reload schema';
