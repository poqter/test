-- =========================================================
-- HWARANG PLATFORM
-- 14 ADMIN CENTER V2 ASSET ADJUSTMENTS v1
--
-- Apply ONCE after 13_Admin_Center_V2_Credit_Buckets.sql.
--
-- Adds / changes only the Admin Center asset-management layer:
-- 1. Training Credit source labels: purchase / promotion_reward / admin_adjustment
-- 2. Training Credit bulk add / deduct / direct-set with per-user result reporting
-- 3. Voice source labels identical to Training Credit
-- 4. Voice ledger source tracking
-- 5. Backward compatibility for legacy bonus and 5-argument Voice RPC callers
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 1. Normalize asset-source metadata.
-- ---------------------------------------------------------
update public.hwarang_ai_credit_ledger
set source_type = 'promotion_reward'
where source_type = 'bonus';

alter table public.hwarang_voice_ledger
    add column if not exists source_type text;

update public.hwarang_voice_ledger
set source_type = case
    when actor_user_id is not null then 'admin_adjustment'
    else 'system'
end
where source_type is null
   or btrim(source_type) = '';

update public.hwarang_voice_ledger
set source_type = 'promotion_reward'
where source_type = 'bonus';

alter table public.hwarang_voice_ledger
    alter column source_type set default 'system';

alter table public.hwarang_voice_ledger
    alter column source_type set not null;

-- ---------------------------------------------------------
-- 2. Individual Training Credit adjustment.
--    Existing signature is retained; legacy bonus is normalized.
-- ---------------------------------------------------------
create or replace function public.admin_adjust_hwarang_purchased_credits(
    p_actor_user_id uuid,
    p_target_user_id uuid,
    p_operation text,
    p_amount bigint,
    p_source_type text default 'purchase',
    p_note text default null
)
returns table(
    monthly_balance_credits bigint,
    purchased_balance_credits bigint,
    total_balance_credits bigint,
    total_reserved_credits bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_account public.hwarang_ai_credit_accounts%rowtype;
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
        raise exception 'INVALID_CREDIT_OPERATION';
    end if;

    if p_operation in ('grant','revoke') and p_amount <= 0 then
        raise exception 'INVALID_CREDIT_AMOUNT';
    end if;

    if p_operation = 'reset' and p_amount < 0 then
        raise exception 'INVALID_CREDIT_AMOUNT';
    end if;

    v_source := lower(coalesce(nullif(btrim(p_source_type),''),'admin_adjustment'));
    if v_source = 'bonus' then
        v_source := 'promotion_reward';
    end if;

    if v_source not in ('purchase','promotion_reward','admin_adjustment','migration') then
        raise exception 'INVALID_CREDIT_SOURCE';
    end if;

    perform private.ensure_hwarang_monthly_credit(p_target_user_id);

    select *
    into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_target_user_id
    for update;

    if p_operation in ('revoke','reset')
       and v_account.purchased_reserved_credits > 0 then
        raise exception 'AI_ACTIVE_PURCHASED_RESERVATION';
    end if;

    if p_operation = 'grant' then
        v_delta := p_amount;

        update public.hwarang_ai_credit_accounts a
        set purchased_balance_credits = a.purchased_balance_credits + p_amount,
            updated_at = now()
        where a.user_id = p_target_user_id
        returning * into v_account;

    elsif p_operation = 'revoke' then
        if p_amount > greatest(
            0::bigint,
            v_account.purchased_balance_credits - v_account.purchased_reserved_credits
        ) then
            raise exception 'PURCHASED_CREDIT_REVOKE_EXCEEDS_AVAILABLE';
        end if;

        v_delta := -p_amount;

        update public.hwarang_ai_credit_accounts a
        set purchased_balance_credits = a.purchased_balance_credits - p_amount,
            updated_at = now()
        where a.user_id = p_target_user_id
        returning * into v_account;

    else
        v_delta := p_amount - v_account.purchased_balance_credits;

        update public.hwarang_ai_credit_accounts a
        set purchased_balance_credits = p_amount,
            purchased_reserved_credits = 0,
            updated_at = now()
        where a.user_id = p_target_user_id
        returning * into v_account;
    end if;

    perform private.sync_hwarang_credit_aggregate(p_target_user_id);

    select *
    into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_target_user_id;

    insert into public.hwarang_ai_credit_ledger(
        user_id,
        entry_type,
        delta_credits,
        balance_after,
        allocation_after,
        actor_user_id,
        note,
        bucket,
        source_type,
        monthly_balance_after,
        purchased_balance_after,
        credit_period
    )
    values (
        p_target_user_id,
        p_operation,
        v_delta,
        v_account.balance_credits,
        v_account.allocation_credits,
        p_actor_user_id,
        nullif(btrim(coalesce(p_note,'')),''),
        'purchased',
        v_source,
        v_account.monthly_balance_credits,
        v_account.purchased_balance_credits,
        v_account.monthly_period
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
        'purchased_credit_' || p_operation,
        jsonb_build_object(
            'amount', p_amount,
            'delta', v_delta,
            'source_type', v_source,
            'purchased_balance_after', v_account.purchased_balance_credits,
            'total_balance_after', v_account.balance_credits,
            'note', p_note
        )
    );

    monthly_balance_credits := v_account.monthly_balance_credits;
    purchased_balance_credits := v_account.purchased_balance_credits;
    total_balance_credits := v_account.balance_credits;
    total_reserved_credits := v_account.reserved_credits;
    return next;
end;
$$;

revoke all on function public.admin_adjust_hwarang_purchased_credits(uuid,uuid,text,bigint,text,text)
from public, anon, authenticated;
grant execute on function public.admin_adjust_hwarang_purchased_credits(uuid,uuid,text,bigint,text,text)
to service_role;

-- ---------------------------------------------------------
-- 3. Generic multi-account Training Credit adjustment.
--    One failing account does not roll back successful accounts.
-- ---------------------------------------------------------
create or replace function public.admin_bulk_adjust_hwarang_purchased_credits(
    p_actor_user_id uuid,
    p_target_user_ids uuid[],
    p_operation text,
    p_amount bigint,
    p_source_type text,
    p_note text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_uid uuid;
    v_source text;
    v_success_count integer := 0;
    v_failed_count integer := 0;
    v_requested_count integer := 0;
    v_results jsonb := '[]'::jsonb;
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

    if p_operation not in ('grant','revoke','reset') then
        raise exception 'INVALID_CREDIT_OPERATION';
    end if;

    if p_operation in ('grant','revoke') and p_amount <= 0 then
        raise exception 'INVALID_CREDIT_AMOUNT';
    end if;

    if p_operation = 'reset' and p_amount < 0 then
        raise exception 'INVALID_CREDIT_AMOUNT';
    end if;

    if coalesce(array_length(p_target_user_ids,1),0) = 0 then
        raise exception 'TARGET_USERS_REQUIRED';
    end if;

    v_source := lower(coalesce(nullif(btrim(p_source_type),''),'admin_adjustment'));
    if v_source = 'bonus' then
        v_source := 'promotion_reward';
    end if;

    if v_source not in ('purchase','promotion_reward','admin_adjustment','migration') then
        raise exception 'INVALID_CREDIT_SOURCE';
    end if;

    select count(distinct x)
    into v_requested_count
    from unnest(p_target_user_ids) as u(x)
    where x is not null;

    if v_requested_count = 0 then
        raise exception 'TARGET_USERS_REQUIRED';
    end if;

    for v_uid in
        select distinct x
        from unnest(p_target_user_ids) as u(x)
        where x is not null
    loop
        begin
            if not exists (
                select 1 from public.profiles where id = v_uid
            ) then
                raise exception 'TARGET_USER_NOT_FOUND';
            end if;

            perform 1
            from public.admin_adjust_hwarang_purchased_credits(
                p_actor_user_id,
                v_uid,
                p_operation,
                p_amount,
                v_source,
                p_note
            );

            v_success_count := v_success_count + 1;
            v_results := v_results || jsonb_build_array(
                jsonb_build_object(
                    'user_id', v_uid,
                    'status', 'success'
                )
            );
        exception when others then
            v_failed_count := v_failed_count + 1;
            v_results := v_results || jsonb_build_array(
                jsonb_build_object(
                    'user_id', v_uid,
                    'status', 'failed',
                    'error', sqlerrm
                )
            );
        end;
    end loop;

    insert into public.hwarang_admin_audit_log(
        actor_user_id,
        action,
        details
    )
    values (
        p_actor_user_id,
        'bulk_purchased_credit_adjustment',
        jsonb_build_object(
            'requested_count', v_requested_count,
            'success_count', v_success_count,
            'failed_count', v_failed_count,
            'operation', p_operation,
            'amount_each', p_amount,
            'source_type', v_source,
            'note', p_note
        )
    );

    return jsonb_build_object(
        'requested_count', v_requested_count,
        'success_count', v_success_count,
        'failed_count', v_failed_count,
        'operation', p_operation,
        'amount_each', p_amount,
        'source_type', v_source,
        'results', v_results
    );
end;
$$;

revoke all on function public.admin_bulk_adjust_hwarang_purchased_credits(uuid,uuid[],text,bigint,text,text)
from public, anon, authenticated;
grant execute on function public.admin_bulk_adjust_hwarang_purchased_credits(uuid,uuid[],text,bigint,text,text)
to service_role;

-- Legacy bulk-grant RPC remains usable by old UI/builds.
create or replace function public.admin_bulk_grant_hwarang_purchased_credits(
    p_actor_user_id uuid,
    p_target_user_ids uuid[],
    p_amount bigint,
    p_source_type text default 'purchase',
    p_note text default null
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_result jsonb;
begin
    v_result := public.admin_bulk_adjust_hwarang_purchased_credits(
        p_actor_user_id,
        p_target_user_ids,
        'grant',
        p_amount,
        p_source_type,
        p_note
    );

    return coalesce((v_result ->> 'success_count')::integer,0);
end;
$$;

revoke all on function public.admin_bulk_grant_hwarang_purchased_credits(uuid,uuid[],bigint,text,text)
from public, anon, authenticated;
grant execute on function public.admin_bulk_grant_hwarang_purchased_credits(uuid,uuid[],bigint,text,text)
to service_role;

-- ---------------------------------------------------------
-- 4. Voice adjustment with the same source classification.
--    The new 6-argument RPC is used by Admin Center V2.
-- ---------------------------------------------------------
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

        update public.hwarang_voice_accounts
        set allocation_seconds = allocation_seconds + v_seconds,
            balance_seconds = balance_seconds + v_seconds,
            updated_at = now()
        where user_id = p_target_user_id
        returning * into v_account;

    elsif p_operation = 'revoke' then
        if v_seconds > greatest(0::bigint, v_account.balance_seconds - v_account.reserved_seconds) then
            raise exception 'VOICE_REVOKE_EXCEEDS_AVAILABLE';
        end if;

        v_delta := -v_seconds;

        update public.hwarang_voice_accounts
        set allocation_seconds = greatest(0::bigint, allocation_seconds - v_seconds),
            balance_seconds = balance_seconds - v_seconds,
            updated_at = now()
        where user_id = p_target_user_id
        returning * into v_account;

    else
        v_delta := v_seconds - v_account.balance_seconds;

        update public.hwarang_voice_accounts
        set allocation_seconds = v_seconds,
            balance_seconds = v_seconds,
            reserved_seconds = 0,
            updated_at = now()
        where user_id = p_target_user_id
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

-- ---------------------------------------------------------
-- 5. Multi-account Voice adjustment.
--    Same operation/source semantics as Training Credit.
-- ---------------------------------------------------------
create or replace function public.admin_bulk_adjust_hwarang_voice_minutes(
    p_actor_user_id uuid,
    p_target_user_ids uuid[],
    p_operation text,
    p_minutes bigint,
    p_source_type text,
    p_note text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_uid uuid;
    v_source text;
    v_success_count integer := 0;
    v_failed_count integer := 0;
    v_requested_count integer := 0;
    v_results jsonb := '[]'::jsonb;
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

    if p_operation not in ('grant','revoke','reset') then
        raise exception 'INVALID_VOICE_OPERATION';
    end if;

    if p_operation in ('grant','revoke') and p_minutes <= 0 then
        raise exception 'INVALID_VOICE_MINUTES';
    end if;

    if p_operation = 'reset' and p_minutes < 0 then
        raise exception 'INVALID_VOICE_MINUTES';
    end if;

    if coalesce(array_length(p_target_user_ids,1),0) = 0 then
        raise exception 'TARGET_USERS_REQUIRED';
    end if;

    v_source := lower(coalesce(nullif(btrim(p_source_type),''),'admin_adjustment'));
    if v_source = 'bonus' then
        v_source := 'promotion_reward';
    end if;

    if v_source not in ('purchase','promotion_reward','admin_adjustment','migration','system') then
        raise exception 'INVALID_VOICE_SOURCE';
    end if;

    select count(distinct x)
    into v_requested_count
    from unnest(p_target_user_ids) as u(x)
    where x is not null;

    if v_requested_count = 0 then
        raise exception 'TARGET_USERS_REQUIRED';
    end if;

    for v_uid in
        select distinct x
        from unnest(p_target_user_ids) as u(x)
        where x is not null
    loop
        begin
            if not exists (
                select 1 from public.profiles where id = v_uid
            ) then
                raise exception 'TARGET_USER_NOT_FOUND';
            end if;

            perform 1
            from public.admin_adjust_hwarang_voice_minutes(
                p_actor_user_id,
                v_uid,
                p_operation,
                p_minutes,
                v_source,
                p_note
            );

            v_success_count := v_success_count + 1;
            v_results := v_results || jsonb_build_array(
                jsonb_build_object(
                    'user_id', v_uid,
                    'status', 'success'
                )
            );
        exception when others then
            v_failed_count := v_failed_count + 1;
            v_results := v_results || jsonb_build_array(
                jsonb_build_object(
                    'user_id', v_uid,
                    'status', 'failed',
                    'error', sqlerrm
                )
            );
        end;
    end loop;

    insert into public.hwarang_admin_audit_log(
        actor_user_id,
        action,
        details
    )
    values (
        p_actor_user_id,
        'bulk_voice_adjustment',
        jsonb_build_object(
            'requested_count', v_requested_count,
            'success_count', v_success_count,
            'failed_count', v_failed_count,
            'operation', p_operation,
            'minutes_each', p_minutes,
            'source_type', v_source,
            'note', p_note
        )
    );

    return jsonb_build_object(
        'requested_count', v_requested_count,
        'success_count', v_success_count,
        'failed_count', v_failed_count,
        'operation', p_operation,
        'minutes_each', p_minutes,
        'source_type', v_source,
        'results', v_results
    );
end;
$$;

revoke all on function public.admin_bulk_adjust_hwarang_voice_minutes(uuid,uuid[],text,bigint,text,text)
from public, anon, authenticated;
grant execute on function public.admin_bulk_adjust_hwarang_voice_minutes(uuid,uuid[],text,bigint,text,text)
to service_role;

-- Keep the existing 5-argument RPC for older builds.
create or replace function public.admin_adjust_hwarang_voice_minutes(
    p_actor_user_id uuid,
    p_target_user_id uuid,
    p_operation text,
    p_minutes bigint,
    p_note text default null
)
returns table(
    allocation_seconds bigint,
    balance_seconds bigint,
    reserved_seconds bigint
)
language sql
security definer
set search_path = ''
as $$
    select *
    from public.admin_adjust_hwarang_voice_minutes(
        p_actor_user_id,
        p_target_user_id,
        p_operation,
        p_minutes,
        'admin_adjustment',
        p_note
    );
$$;

revoke all on function public.admin_adjust_hwarang_voice_minutes(uuid,uuid,text,bigint,text)
from public, anon, authenticated;
grant execute on function public.admin_adjust_hwarang_voice_minutes(uuid,uuid,text,bigint,text)
to service_role;

commit;

-- Refresh PostgREST RPC/schema metadata in Supabase.
notify pgrst, 'reload schema';
