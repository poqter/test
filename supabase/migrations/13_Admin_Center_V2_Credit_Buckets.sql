-- =========================================================
-- HWARANG PLATFORM
-- 13 ADMIN CENTER V2 + MONTHLY / PURCHASED CREDIT BUCKETS
--
-- Apply ONCE after 12_Login_Fast_Path.sql.
-- No OpenAI key is required.
--
-- Final credit policy:
-- - Monthly free Training Credit resets to the configured base every KST month.
-- - Unused monthly free credit does NOT carry over.
-- - Purchased / permanent Training Credit never expires.
-- - Monthly free credit is always consumed before purchased credit.
-- - Voice allowance remains separate and persistent.
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 1. Administrator-editable credit / budget policy.
-- soft_limit_percent in hwarang_ai_runtime_config is retained only for legacy
-- compatibility; remaining_warning_percent is the new source of truth.
-- ---------------------------------------------------------
create table if not exists public.hwarang_credit_policy (
    config_id smallint primary key default 1 check (config_id = 1),
    monthly_free_credits bigint not null default 1000
        check (monthly_free_credits >= 0),
    remaining_warning_percent integer not null default 20
        check (remaining_warning_percent between 1 and 99),
    default_voice_minutes integer not null default 0
        check (default_voice_minutes >= 0),
    monthly_ai_budget_usd numeric(18,4) not null default 50
        check (monthly_ai_budget_usd >= 0),
    budget_warning_percent integer not null default 80
        check (budget_warning_percent between 1 and 99),
    timezone_name text not null default 'Asia/Seoul',
    updated_by uuid references public.profiles(id) on delete set null,
    updated_at timestamptz not null default now()
);

insert into public.hwarang_credit_policy(
    config_id,
    monthly_free_credits,
    remaining_warning_percent,
    default_voice_minutes,
    monthly_ai_budget_usd,
    budget_warning_percent,
    timezone_name
)
select
    1,
    1000,
    greatest(1, least(99, 100 - coalesce(c.soft_limit_percent,80))),
    0,
    50,
    80,
    'Asia/Seoul'
from public.hwarang_ai_runtime_config c
where c.config_id = 1
on conflict (config_id) do nothing;

-- ---------------------------------------------------------
-- 2. Split Training Credit into monthly-free and purchased buckets.
-- Existing unspent credit is preserved as purchased/permanent credit.
-- ---------------------------------------------------------
alter table public.hwarang_ai_credit_accounts
    add column if not exists monthly_period date,
    add column if not exists monthly_grant_credits bigint,
    add column if not exists monthly_balance_credits bigint,
    add column if not exists monthly_reserved_credits bigint,
    add column if not exists purchased_balance_credits bigint,
    add column if not exists purchased_reserved_credits bigint;

-- Request rows remember which bucket was reserved/charged.
alter table public.hwarang_ai_request_registry
    add column if not exists reserved_monthly_credits bigint,
    add column if not exists reserved_purchased_credits bigint,
    add column if not exists actual_monthly_credits bigint,
    add column if not exists actual_purchased_credits bigint;

-- Credit ledger gains bucket/source metadata without invalidating legacy rows.
alter table public.hwarang_ai_credit_ledger
    add column if not exists bucket text,
    add column if not exists source_type text,
    add column if not exists monthly_balance_after bigint,
    add column if not exists purchased_balance_after bigint,
    add column if not exists credit_period date;

-- Initialize existing accounts exactly once. Any old unspent balance is treated
-- as permanent/purchased so migration can never make it disappear next month.
with policy as (
    select * from public.hwarang_credit_policy where config_id = 1
), current_period as (
    select date_trunc('month', now() at time zone 'Asia/Seoul')::date as period_start
)
update public.hwarang_ai_credit_accounts a
set
    monthly_period = cp.period_start,
    monthly_grant_credits = p.monthly_free_credits,
    monthly_balance_credits = p.monthly_free_credits,
    monthly_reserved_credits = 0,
    purchased_balance_credits = greatest(0, coalesce(a.balance_credits,0)),
    purchased_reserved_credits = greatest(0, coalesce(a.reserved_credits,0)),
    balance_credits = p.monthly_free_credits + greatest(0, coalesce(a.balance_credits,0)),
    reserved_credits = greatest(0, coalesce(a.reserved_credits,0)),
    allocation_credits = greatest(
        p.monthly_free_credits + greatest(0, coalesce(a.balance_credits,0)),
        p.monthly_free_credits
    ),
    updated_at = now()
from policy p, current_period cp
where a.monthly_period is null;

alter table public.hwarang_ai_credit_accounts
    alter column monthly_period set default (date_trunc('month', now() at time zone 'Asia/Seoul')::date),
    alter column monthly_period set not null,
    alter column monthly_grant_credits set default 0,
    alter column monthly_grant_credits set not null,
    alter column monthly_balance_credits set default 0,
    alter column monthly_balance_credits set not null,
    alter column monthly_reserved_credits set default 0,
    alter column monthly_reserved_credits set not null,
    alter column purchased_balance_credits set default 0,
    alter column purchased_balance_credits set not null,
    alter column purchased_reserved_credits set default 0,
    alter column purchased_reserved_credits set not null;

-- Preserve any in-flight legacy Training reservation as permanent-bucket reserve
-- before tightening the new columns to NOT NULL.
update public.hwarang_ai_request_registry
set
    reserved_monthly_credits = coalesce(reserved_monthly_credits,0),
    reserved_purchased_credits = case
        when billing_bucket = 'TRAINING'
         and reserved_credits > 0
         and coalesce(reserved_monthly_credits,0) = 0
         and coalesce(reserved_purchased_credits,0) = 0
        then reserved_credits
        else coalesce(reserved_purchased_credits,0)
    end,
    actual_monthly_credits = coalesce(actual_monthly_credits,0),
    actual_purchased_credits = coalesce(actual_purchased_credits,0);

alter table public.hwarang_ai_request_registry
    alter column reserved_monthly_credits set default 0,
    alter column reserved_monthly_credits set not null,
    alter column reserved_purchased_credits set default 0,
    alter column reserved_purchased_credits set not null,
    alter column actual_monthly_credits set default 0,
    alter column actual_monthly_credits set not null,
    alter column actual_purchased_credits set default 0,
    alter column actual_purchased_credits set not null;

-- Named constraints are added only once.
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'hwarang_ai_credit_monthly_nonnegative'
          and conrelid = 'public.hwarang_ai_credit_accounts'::regclass
    ) then
        alter table public.hwarang_ai_credit_accounts
        add constraint hwarang_ai_credit_monthly_nonnegative
        check (
            monthly_grant_credits >= 0
            and monthly_balance_credits >= 0
            and monthly_reserved_credits >= 0
            and monthly_reserved_credits <= monthly_balance_credits
        );
    end if;

    if not exists (
        select 1 from pg_constraint
        where conname = 'hwarang_ai_credit_purchased_nonnegative'
          and conrelid = 'public.hwarang_ai_credit_accounts'::regclass
    ) then
        alter table public.hwarang_ai_credit_accounts
        add constraint hwarang_ai_credit_purchased_nonnegative
        check (
            purchased_balance_credits >= 0
            and purchased_reserved_credits >= 0
            and purchased_reserved_credits <= purchased_balance_credits
        );
    end if;

    if not exists (
        select 1 from pg_constraint
        where conname = 'hwarang_ai_request_credit_buckets_nonnegative'
          and conrelid = 'public.hwarang_ai_request_registry'::regclass
    ) then
        alter table public.hwarang_ai_request_registry
        add constraint hwarang_ai_request_credit_buckets_nonnegative
        check (
            reserved_monthly_credits >= 0
            and reserved_purchased_credits >= 0
            and actual_monthly_credits >= 0
            and actual_purchased_credits >= 0
        );
    end if;
end
$$;

-- ---------------------------------------------------------
-- 3. Monthly-credit helpers.
-- ---------------------------------------------------------
create or replace function private.hwarang_credit_period()
returns date
language sql
stable
set search_path = ''
as $$
    select date_trunc('month', now() at time zone 'Asia/Seoul')::date;
$$;

revoke all on function private.hwarang_credit_period() from public;
grant execute on function private.hwarang_credit_period() to service_role;

create or replace function private.sync_hwarang_credit_aggregate(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    update public.hwarang_ai_credit_accounts a
    set
        balance_credits = a.monthly_balance_credits + a.purchased_balance_credits,
        reserved_credits = a.monthly_reserved_credits + a.purchased_reserved_credits,
        allocation_credits = greatest(
            a.monthly_grant_credits,
            a.monthly_balance_credits + a.purchased_balance_credits
        ),
        updated_at = now()
    where a.user_id = p_user_id;
end;
$$;

revoke all on function private.sync_hwarang_credit_aggregate(uuid) from public;

create or replace function private.ensure_hwarang_monthly_credit(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_policy public.hwarang_credit_policy%rowtype;
    v_account public.hwarang_ai_credit_accounts%rowtype;
    v_period date;
    v_old_monthly bigint;
    v_total_after bigint;
begin
    select * into v_policy
    from public.hwarang_credit_policy
    where config_id = 1;

    if not found then
        raise exception 'CREDIT_POLICY_NOT_CONFIGURED';
    end if;

    v_period := private.hwarang_credit_period();

    insert into public.hwarang_ai_credit_accounts(
        user_id,
        monthly_period,
        monthly_grant_credits,
        monthly_balance_credits,
        monthly_reserved_credits,
        purchased_balance_credits,
        purchased_reserved_credits,
        allocation_credits,
        balance_credits,
        reserved_credits
    )
    values (
        p_user_id,
        v_period,
        v_policy.monthly_free_credits,
        v_policy.monthly_free_credits,
        0,
        0,
        0,
        v_policy.monthly_free_credits,
        v_policy.monthly_free_credits,
        0
    )
    on conflict (user_id) do nothing;

    select * into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_user_id
    for update;

    if v_account.monthly_period < v_period
       and v_account.monthly_reserved_credits = 0 then
        v_old_monthly := v_account.monthly_balance_credits;

        update public.hwarang_ai_credit_accounts a
        set
            monthly_period = v_period,
            monthly_grant_credits = v_policy.monthly_free_credits,
            monthly_balance_credits = v_policy.monthly_free_credits,
            monthly_reserved_credits = 0,
            updated_at = now()
        where a.user_id = p_user_id
        returning * into v_account;

        perform private.sync_hwarang_credit_aggregate(p_user_id);

        select balance_credits into v_total_after
        from public.hwarang_ai_credit_accounts
        where user_id = p_user_id;

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
            p_user_id,
            'reset',
            v_policy.monthly_free_credits - coalesce(v_old_monthly,0),
            v_total_after,
            greatest(v_account.monthly_grant_credits, v_total_after),
            null,
            'Monthly free Training Credit reset (KST)',
            'monthly',
            'monthly_reset',
            v_account.monthly_balance_credits,
            v_account.purchased_balance_credits,
            v_period
        );
    else
        perform private.sync_hwarang_credit_aggregate(p_user_id);
    end if;
end;
$$;

revoke all on function private.ensure_hwarang_monthly_credit(uuid) from public;

-- New users receive the current monthly base immediately.
create or replace function private.ensure_hwarang_ai_credit_account()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_policy public.hwarang_credit_policy%rowtype;
    v_period date;
    v_inserted uuid;
begin
    select * into v_policy
    from public.hwarang_credit_policy
    where config_id = 1;

    v_period := private.hwarang_credit_period();

    insert into public.hwarang_ai_credit_accounts(
        user_id,
        monthly_period,
        monthly_grant_credits,
        monthly_balance_credits,
        monthly_reserved_credits,
        purchased_balance_credits,
        purchased_reserved_credits,
        allocation_credits,
        balance_credits,
        reserved_credits
    )
    values (
        new.id,
        v_period,
        coalesce(v_policy.monthly_free_credits,1000),
        coalesce(v_policy.monthly_free_credits,1000),
        0,
        0,
        0,
        coalesce(v_policy.monthly_free_credits,1000),
        coalesce(v_policy.monthly_free_credits,1000),
        0
    )
    on conflict (user_id) do nothing
    returning user_id into v_inserted;

    if v_inserted is not null then
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
            new.id,
            'grant',
            coalesce(v_policy.monthly_free_credits,1000),
            coalesce(v_policy.monthly_free_credits,1000),
            coalesce(v_policy.monthly_free_credits,1000),
            null,
            'Initial monthly free Training Credit',
            'monthly',
            'monthly_initial',
            coalesce(v_policy.monthly_free_credits,1000),
            0,
            v_period
        );
    end if;

    return new;
end;
$$;

revoke all on function private.ensure_hwarang_ai_credit_account() from public;

-- Voice default applies only when a brand-new account is created; existing
-- Voice balances are never reset by the monthly Training Credit policy.
create or replace function private.ensure_hwarang_voice_account()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_minutes integer;
    v_inserted uuid;
begin
    select default_voice_minutes into v_minutes
    from public.hwarang_credit_policy
    where config_id = 1;

    v_minutes := coalesce(v_minutes,0);

    insert into public.hwarang_voice_accounts(
        user_id,
        allocation_seconds,
        balance_seconds,
        reserved_seconds,
        updated_at
    )
    values (
        new.id,
        v_minutes * 60,
        v_minutes * 60,
        0,
        now()
    )
    on conflict (user_id) do nothing
    returning user_id into v_inserted;

    if v_inserted is not null and v_minutes > 0 then
        insert into public.hwarang_voice_ledger(
            user_id,
            entry_type,
            delta_seconds,
            balance_after_seconds,
            allocation_after_seconds,
            actor_user_id,
            note
        )
        values (
            new.id,
            'grant',
            v_minutes * 60,
            v_minutes * 60,
            v_minutes * 60,
            null,
            'Initial Voice allowance'
        );
    end if;

    return new;
end;
$$;

revoke all on function private.ensure_hwarang_voice_account() from public;

-- ---------------------------------------------------------
-- 4. User-facing entitlement status (monthly + purchased breakdown).
-- ---------------------------------------------------------
drop function if exists public.get_hwarang_ai_entitlement_status(uuid);

create function public.get_hwarang_ai_entitlement_status(p_user_id uuid)
returns table(
    training_allocation_credits bigint,
    training_balance_credits bigint,
    training_reserved_credits bigint,
    training_available_credits bigint,
    training_remaining_percent numeric,

    monthly_credit_period date,
    monthly_grant_credits bigint,
    monthly_balance_credits bigint,
    monthly_reserved_credits bigint,
    monthly_available_credits bigint,
    purchased_balance_credits bigint,
    purchased_reserved_credits bigint,
    purchased_available_credits bigint,
    training_warning_threshold_credits bigint,
    training_low boolean,

    voice_allocation_seconds bigint,
    voice_balance_seconds bigint,
    voice_reserved_seconds bigint,
    voice_available_seconds bigint,
    voice_remaining_percent numeric,
    voice_low boolean,

    service_enabled boolean,
    text_enabled boolean,
    voice_enabled boolean,
    assessment_enabled boolean,
    soft_limit_percent integer,
    remaining_warning_percent integer,
    contact_label text,
    contact_url text
)
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform private.ensure_hwarang_monthly_credit(p_user_id);

    return query
    select
        a.allocation_credits,
        a.balance_credits,
        a.reserved_credits,
        greatest(0::bigint, a.balance_credits - a.reserved_credits),
        case
            when a.monthly_grant_credits > 0 then
                round(least(
                    100::numeric,
                    greatest(0::numeric,
                        (a.balance_credits - a.reserved_credits)::numeric
                        / a.monthly_grant_credits::numeric * 100
                    )
                ),1)
            when (a.balance_credits - a.reserved_credits) > 0 then 100::numeric
            else 0::numeric
        end,

        a.monthly_period,
        a.monthly_grant_credits,
        a.monthly_balance_credits,
        a.monthly_reserved_credits,
        greatest(0::bigint, a.monthly_balance_credits - a.monthly_reserved_credits),
        a.purchased_balance_credits,
        a.purchased_reserved_credits,
        greatest(0::bigint, a.purchased_balance_credits - a.purchased_reserved_credits),
        floor(a.monthly_grant_credits * cp.remaining_warning_percent / 100.0)::bigint,
        (
            a.monthly_grant_credits > 0
            and greatest(0::bigint, a.balance_credits - a.reserved_credits)
                <= floor(a.monthly_grant_credits * cp.remaining_warning_percent / 100.0)::bigint
        ),

        va.allocation_seconds,
        va.balance_seconds,
        va.reserved_seconds,
        greatest(0::bigint, va.balance_seconds - va.reserved_seconds),
        case
            when va.allocation_seconds <= 0 then 0::numeric
            else round(
                greatest(0::numeric,
                    (va.balance_seconds - va.reserved_seconds)::numeric
                    / va.allocation_seconds::numeric * 100
                ),1
            )
        end,
        case
            when va.allocation_seconds <= 0 then false
            else (
                (va.balance_seconds - va.reserved_seconds)::numeric
                / va.allocation_seconds::numeric * 100
            ) <= cp.remaining_warning_percent
        end,

        cfg.service_enabled,
        cfg.text_enabled,
        cfg.voice_enabled,
        cfg.assessment_enabled,
        cfg.soft_limit_percent,
        cp.remaining_warning_percent,
        cfg.contact_label,
        cfg.contact_url
    from public.hwarang_ai_credit_accounts a
    join public.hwarang_voice_accounts va
      on va.user_id = a.user_id
    cross join public.hwarang_ai_runtime_config cfg
    cross join public.hwarang_credit_policy cp
    where a.user_id = p_user_id
      and cfg.config_id = 1
      and cp.config_id = 1;
end;
$$;

revoke all on function public.get_hwarang_ai_entitlement_status(uuid)
from public, anon, authenticated;
grant execute on function public.get_hwarang_ai_entitlement_status(uuid)
to service_role;

-- ---------------------------------------------------------
-- 5. Credit policy management.
-- Policy changes affect new users immediately and existing users on their next
-- monthly reset; they do not retroactively rewrite the current month's grant.
-- ---------------------------------------------------------
create or replace function public.admin_update_hwarang_credit_policy(
    p_actor_user_id uuid,
    p_monthly_free_credits bigint,
    p_remaining_warning_percent integer,
    p_default_voice_minutes integer,
    p_monthly_ai_budget_usd numeric,
    p_budget_warning_percent integer
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    if not exists (
        select 1 from public.profiles
        where id = p_actor_user_id
          and role = 'super_admin'
          and is_active = true
    ) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;

    if p_monthly_free_credits < 0 then raise exception 'INVALID_MONTHLY_FREE_CREDITS'; end if;
    if p_remaining_warning_percent not between 1 and 99 then raise exception 'INVALID_REMAINING_WARNING_PERCENT'; end if;
    if p_default_voice_minutes < 0 then raise exception 'INVALID_DEFAULT_VOICE_MINUTES'; end if;
    if p_monthly_ai_budget_usd < 0 then raise exception 'INVALID_MONTHLY_AI_BUDGET'; end if;
    if p_budget_warning_percent not between 1 and 99 then raise exception 'INVALID_BUDGET_WARNING_PERCENT'; end if;

    update public.hwarang_credit_policy
    set
        monthly_free_credits = p_monthly_free_credits,
        remaining_warning_percent = p_remaining_warning_percent,
        default_voice_minutes = p_default_voice_minutes,
        monthly_ai_budget_usd = p_monthly_ai_budget_usd,
        budget_warning_percent = p_budget_warning_percent,
        updated_by = p_actor_user_id,
        updated_at = now()
    where config_id = 1;

    -- Legacy mirror only. New code reads remaining_warning_percent above.
    update public.hwarang_ai_runtime_config
    set
        soft_limit_percent = greatest(1, least(99, 100 - p_remaining_warning_percent)),
        updated_by = p_actor_user_id,
        updated_at = now()
    where config_id = 1;

    insert into public.hwarang_admin_audit_log(actor_user_id, action, details)
    values (
        p_actor_user_id,
        'credit_policy_updated',
        jsonb_build_object(
            'monthly_free_credits', p_monthly_free_credits,
            'remaining_warning_percent', p_remaining_warning_percent,
            'default_voice_minutes', p_default_voice_minutes,
            'monthly_ai_budget_usd', p_monthly_ai_budget_usd,
            'budget_warning_percent', p_budget_warning_percent
        )
    );
end;
$$;

revoke all on function public.admin_update_hwarang_credit_policy(uuid,bigint,integer,integer,numeric,integer)
from public, anon, authenticated;
grant execute on function public.admin_update_hwarang_credit_policy(uuid,bigint,integer,integer,numeric,integer)
to service_role;

-- ---------------------------------------------------------
-- 6. Purchased/permanent credit management.
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
        select 1 from public.profiles
        where id = p_actor_user_id
          and role = 'super_admin'
          and is_active = true
    ) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;

    if p_operation not in ('grant','revoke','reset') then
        raise exception 'INVALID_CREDIT_OPERATION';
    end if;
    if p_amount < 0 then raise exception 'INVALID_CREDIT_AMOUNT'; end if;

    v_source := lower(coalesce(nullif(btrim(p_source_type),''),'purchase'));
    if v_source not in ('purchase','bonus','admin_adjustment','migration') then
        raise exception 'INVALID_CREDIT_SOURCE';
    end if;

    perform private.ensure_hwarang_monthly_credit(p_target_user_id);

    select * into v_account
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
        if p_amount > (v_account.purchased_balance_credits - v_account.purchased_reserved_credits) then
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

    select * into v_account
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

    insert into public.hwarang_admin_audit_log(actor_user_id,target_user_id,action,details)
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

-- Backward-compatible admin RPC: all manual grants are now permanent bucket.
create or replace function public.admin_adjust_hwarang_ai_credits(
    p_actor_user_id uuid,
    p_target_user_id uuid,
    p_operation text,
    p_amount bigint,
    p_note text default null
)
returns table(allocation_credits bigint,balance_credits bigint,reserved_credits bigint)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_account public.hwarang_ai_credit_accounts%rowtype;
begin
    perform 1 from public.admin_adjust_hwarang_purchased_credits(
        p_actor_user_id,
        p_target_user_id,
        p_operation,
        p_amount,
        'admin_adjustment',
        p_note
    );

    select * into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_target_user_id;

    allocation_credits := v_account.allocation_credits;
    balance_credits := v_account.balance_credits;
    reserved_credits := v_account.reserved_credits;
    return next;
end;
$$;

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
    v_uid uuid;
    v_count integer := 0;
begin
    if not exists (
        select 1 from public.profiles
        where id = p_actor_user_id
          and role = 'super_admin'
          and is_active = true
    ) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;

    if p_amount <= 0 then raise exception 'INVALID_CREDIT_AMOUNT'; end if;
    if coalesce(array_length(p_target_user_ids,1),0) = 0 then raise exception 'TARGET_USERS_REQUIRED'; end if;

    foreach v_uid in array p_target_user_ids loop
        if exists (select 1 from public.profiles where id = v_uid) then
            perform 1 from public.admin_adjust_hwarang_purchased_credits(
                p_actor_user_id,
                v_uid,
                'grant',
                p_amount,
                p_source_type,
                p_note
            );
            v_count := v_count + 1;
        end if;
    end loop;

    insert into public.hwarang_admin_audit_log(actor_user_id,action,details)
    values (
        p_actor_user_id,
        'bulk_purchased_credit_grant',
        jsonb_build_object(
            'target_count', v_count,
            'amount_each', p_amount,
            'source_type', p_source_type,
            'note', p_note
        )
    );

    return v_count;
end;
$$;

revoke all on function public.admin_bulk_grant_hwarang_purchased_credits(uuid,uuid[],bigint,text,text)
from public, anon, authenticated;
grant execute on function public.admin_bulk_grant_hwarang_purchased_credits(uuid,uuid[],bigint,text,text)
to service_role;

-- ---------------------------------------------------------
-- 7. Reservation cleanup releases the correct Training bucket.
-- ---------------------------------------------------------
create or replace function private.prune_hwarang_ai_reservations()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    r record;
begin
    for r in
        select
            request_id,
            user_id,
            billing_bucket,
            reserved_credits,
            reserved_voice_seconds,
            reserved_monthly_credits,
            reserved_purchased_credits
        from public.hwarang_ai_request_registry
        where status in ('reserved','processing')
          and expires_at < now()
        for update skip locked
    loop
        if r.billing_bucket = 'VOICE' then
            update public.hwarang_voice_accounts
            set reserved_seconds = greatest(0, reserved_seconds - r.reserved_voice_seconds),
                updated_at = now()
            where user_id = r.user_id;
        else
            update public.hwarang_ai_credit_accounts
            set
                monthly_reserved_credits = greatest(0, monthly_reserved_credits - r.reserved_monthly_credits),
                purchased_reserved_credits = greatest(0, purchased_reserved_credits - r.reserved_purchased_credits),
                updated_at = now()
            where user_id = r.user_id;

            perform private.sync_hwarang_credit_aggregate(r.user_id);
            perform private.ensure_hwarang_monthly_credit(r.user_id);
        end if;

        update public.hwarang_ai_request_registry
        set status = 'expired',
            completed_at = now()
        where request_id = r.request_id;
    end loop;
end;
$$;

revoke all on function private.prune_hwarang_ai_reservations() from public;

-- ---------------------------------------------------------
-- 8. TEXT / COACH / EVALUATOR reservation.
-- Monthly credit is reserved first; purchased credit is touched only when the
-- monthly bucket is insufficient.
-- ---------------------------------------------------------
create or replace function public.reserve_hwarang_ai_request(
    p_user_id uuid,
    p_academy_session_id uuid,
    p_turn_no integer,
    p_purpose text,
    p_interaction_mode text,
    p_idempotency_key text,
    p_estimated_credits bigint
)
returns table(
    request_id uuid,
    request_status text,
    duplicate boolean,
    available_credits bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_config public.hwarang_ai_runtime_config%rowtype;
    v_account public.hwarang_ai_credit_accounts%rowtype;
    v_request public.hwarang_ai_request_registry%rowtype;
    v_permissions text[];
    v_lock_reason text;
    v_block_id uuid;
    v_monthly_available bigint;
    v_purchased_available bigint;
    v_reserve_monthly bigint;
    v_reserve_purchased bigint;
begin
    perform private.prune_hwarang_ai_reservations();

    if p_purpose not in ('CUSTOMER','COACH','EVALUATOR') then
        if p_purpose = 'VOICE' then raise exception 'VOICE_USE_SEPARATE_ALLOWANCE'; end if;
        raise exception 'INVALID_AI_PURPOSE';
    end if;
    if p_interaction_mode <> 'TEXT' then raise exception 'TEXT_RESERVATION_REQUIRES_TEXT_MODE'; end if;
    if p_estimated_credits <= 0 then raise exception 'INVALID_CREDIT_ESTIMATE'; end if;
    if p_idempotency_key is null
       or btrim(p_idempotency_key) = ''
       or char_length(p_idempotency_key) > 180 then
        raise exception 'INVALID_IDEMPOTENCY_KEY';
    end if;

    select * into v_request
    from public.hwarang_ai_request_registry
    where idempotency_key = btrim(p_idempotency_key);

    if found then
        if v_request.user_id <> p_user_id then raise exception 'IDEMPOTENCY_KEY_CONFLICT'; end if;
        perform private.ensure_hwarang_monthly_credit(p_user_id);
        select greatest(0,balance_credits-reserved_credits)
        into available_credits
        from public.hwarang_ai_credit_accounts
        where user_id = p_user_id;
        request_id := v_request.request_id;
        request_status := v_request.status;
        duplicate := true;
        available_credits := coalesce(available_credits,0);
        return next;
        return;
    end if;

    if not exists (
        select 1 from public.profiles
        where id = p_user_id and is_active = true
    ) then raise exception 'INACTIVE_USER'; end if;

    select * into v_config
    from public.hwarang_ai_runtime_config
    where config_id = 1;

    if not v_config.service_enabled then raise exception 'AI_SERVICE_DISABLED'; end if;
    if not v_config.text_enabled then raise exception 'AI_TEXT_DISABLED'; end if;
    if p_purpose = 'EVALUATOR' and not v_config.assessment_enabled then
        raise exception 'AI_ASSESSMENT_DISABLED';
    end if;

    select array_agg(permission_code)
    into v_permissions
    from public.get_hwarang_effective_permissions(p_user_id);

    if not ('academy.simulator' = any(coalesce(v_permissions,array[]::text[]))) then
        raise exception 'AI_SIMULATOR_PERMISSION_REQUIRED';
    end if;
    if p_purpose = 'EVALUATOR'
       and not ('academy.formal_ai_assessment' = any(coalesce(v_permissions,array[]::text[]))) then
        raise exception 'AI_ASSESSMENT_PERMISSION_REQUIRED';
    end if;

    if not exists (
        select 1 from public.academy_sessions s
        where s.id = p_academy_session_id
          and s.user_id = p_user_id
          and s.status = 'in_progress'
    ) then raise exception 'ACADEMY_SESSION_INVALID_OR_CLOSED'; end if;

    perform private.ensure_hwarang_monthly_credit(p_user_id);

    select * into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_user_id
    for update;

    v_monthly_available := greatest(0, v_account.monthly_balance_credits - v_account.monthly_reserved_credits);
    v_purchased_available := greatest(0, v_account.purchased_balance_credits - v_account.purchased_reserved_credits);

    if (v_monthly_available + v_purchased_available) < p_estimated_credits then
        v_block_id := private.register_hwarang_ai_block(
            p_user_id,
            p_academy_session_id,
            p_turn_no,
            p_purpose,
            'TEXT',
            'TRAINING',
            p_idempotency_key,
            'training_credit_exhausted',
            case when p_purpose = 'EVALUATOR'
                 then 'academy.formal_ai_assessment'
                 else 'academy.simulator' end
        );

        request_id := v_block_id;
        request_status := 'blocked';
        duplicate := false;
        available_credits := v_monthly_available + v_purchased_available;
        return next;
        return;
    end if;

    v_lock_reason := private.claim_hwarang_ai_session(
        p_user_id,
        p_academy_session_id,
        1200
    );

    if v_lock_reason is not null then
        v_block_id := private.register_hwarang_ai_block(
            p_user_id,
            p_academy_session_id,
            p_turn_no,
            p_purpose,
            'TEXT',
            'TRAINING',
            p_idempotency_key,
            v_lock_reason,
            case when p_purpose = 'EVALUATOR'
                 then 'academy.formal_ai_assessment'
                 else 'academy.simulator' end
        );

        request_id := v_block_id;
        request_status := 'blocked';
        duplicate := false;
        available_credits := v_monthly_available + v_purchased_available;
        return next;
        return;
    end if;

    v_reserve_monthly := least(p_estimated_credits, v_monthly_available);
    v_reserve_purchased := p_estimated_credits - v_reserve_monthly;

    insert into public.hwarang_ai_request_registry(
        idempotency_key,
        user_id,
        academy_session_id,
        turn_no,
        purpose,
        interaction_mode,
        billing_bucket,
        status,
        reserved_credits,
        reserved_voice_seconds,
        reserved_monthly_credits,
        reserved_purchased_credits,
        expires_at
    )
    values (
        btrim(p_idempotency_key),
        p_user_id,
        p_academy_session_id,
        p_turn_no,
        p_purpose,
        'TEXT',
        'TRAINING',
        'reserved',
        p_estimated_credits,
        0,
        v_reserve_monthly,
        v_reserve_purchased,
        now() + interval '10 minutes'
    )
    on conflict (idempotency_key) do nothing
    returning * into v_request;

    if not found then
        select * into v_request
        from public.hwarang_ai_request_registry
        where idempotency_key = btrim(p_idempotency_key);

        if v_request.user_id <> p_user_id then raise exception 'IDEMPOTENCY_KEY_CONFLICT'; end if;

        request_id := v_request.request_id;
        request_status := v_request.status;
        duplicate := true;
        available_credits := v_monthly_available + v_purchased_available;
        return next;
        return;
    end if;

    update public.hwarang_ai_credit_accounts a
    set
        monthly_reserved_credits = a.monthly_reserved_credits + v_reserve_monthly,
        purchased_reserved_credits = a.purchased_reserved_credits + v_reserve_purchased,
        updated_at = now()
    where a.user_id = p_user_id;

    perform private.sync_hwarang_credit_aggregate(p_user_id);

    select * into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_user_id;

    request_id := v_request.request_id;
    request_status := v_request.status;
    duplicate := false;
    available_credits := greatest(
        0,
        v_account.balance_credits - v_account.reserved_credits
    );
    return next;
end;
$$;

-- ---------------------------------------------------------
-- 9. Finalize Training request using monthly-first consumption.
-- ---------------------------------------------------------
create or replace function public.finalize_hwarang_ai_request(
    p_request_id uuid,
    p_result_status text,
    p_actual_credits bigint
)
returns table(balance_credits bigint,reserved_credits bigint,available_credits bigint)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_request public.hwarang_ai_request_registry%rowtype;
    v_account public.hwarang_ai_credit_accounts%rowtype;
    v_other_monthly_reserved bigint;
    v_other_purchased_reserved bigint;
    v_monthly_consumable bigint;
    v_purchased_consumable bigint;
    v_actual_monthly bigint;
    v_actual_purchased bigint;
begin
    if p_result_status not in ('completed','failed') then raise exception 'INVALID_AI_RESULT_STATUS'; end if;
    if p_actual_credits < 0 then raise exception 'INVALID_CREDIT_AMOUNT'; end if;

    select * into v_request
    from public.hwarang_ai_request_registry
    where request_id = p_request_id
    for update;

    if not found then raise exception 'AI_REQUEST_NOT_FOUND'; end if;

    if v_request.status in ('completed','failed','expired','blocked') then
        perform private.ensure_hwarang_monthly_credit(v_request.user_id);
        select a.balance_credits,a.reserved_credits,
               greatest(0,a.balance_credits-a.reserved_credits)
        into balance_credits,reserved_credits,available_credits
        from public.hwarang_ai_credit_accounts a
        where a.user_id = v_request.user_id;
        return next;
        return;
    end if;

    select * into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = v_request.user_id
    for update;

    v_other_monthly_reserved := greatest(
        0,
        v_account.monthly_reserved_credits - v_request.reserved_monthly_credits
    );
    v_other_purchased_reserved := greatest(
        0,
        v_account.purchased_reserved_credits - v_request.reserved_purchased_credits
    );

    if p_result_status = 'completed' then
        v_monthly_consumable := greatest(
            0,
            v_account.monthly_balance_credits - v_other_monthly_reserved
        );
        v_actual_monthly := least(p_actual_credits, v_monthly_consumable);
        v_actual_purchased := p_actual_credits - v_actual_monthly;

        v_purchased_consumable := greatest(
            0,
            v_account.purchased_balance_credits - v_other_purchased_reserved
        );
        if v_actual_purchased > v_purchased_consumable then
            raise exception 'AI_CREDIT_RECONCILE_FAILED';
        end if;

        update public.hwarang_ai_credit_accounts a
        set
            monthly_balance_credits = a.monthly_balance_credits - v_actual_monthly,
            purchased_balance_credits = a.purchased_balance_credits - v_actual_purchased,
            monthly_reserved_credits = v_other_monthly_reserved,
            purchased_reserved_credits = v_other_purchased_reserved,
            updated_at = now()
        where a.user_id = v_request.user_id
        returning * into v_account;

        perform private.sync_hwarang_credit_aggregate(v_request.user_id);
        select * into v_account
        from public.hwarang_ai_credit_accounts
        where user_id = v_request.user_id;

        if v_actual_monthly > 0 then
            insert into public.hwarang_ai_credit_ledger(
                user_id,entry_type,delta_credits,balance_after,allocation_after,request_id,
                note,bucket,source_type,monthly_balance_after,purchased_balance_after,credit_period
            ) values (
                v_request.user_id,'consume',-v_actual_monthly,
                v_account.balance_credits,v_account.allocation_credits,v_request.request_id,
                'AI training usage - monthly free','monthly','ai_usage',
                v_account.monthly_balance_credits,v_account.purchased_balance_credits,v_account.monthly_period
            );
        end if;

        if v_actual_purchased > 0 then
            insert into public.hwarang_ai_credit_ledger(
                user_id,entry_type,delta_credits,balance_after,allocation_after,request_id,
                note,bucket,source_type,monthly_balance_after,purchased_balance_after,credit_period
            ) values (
                v_request.user_id,'consume',-v_actual_purchased,
                v_account.balance_credits,v_account.allocation_credits,v_request.request_id,
                'AI training usage - purchased','purchased','ai_usage',
                v_account.monthly_balance_credits,v_account.purchased_balance_credits,v_account.monthly_period
            );
        end if;

        update public.hwarang_ai_request_registry
        set
            status = 'completed',
            actual_credits = p_actual_credits,
            actual_monthly_credits = v_actual_monthly,
            actual_purchased_credits = v_actual_purchased,
            completed_at = now()
        where request_id = p_request_id;
    else
        update public.hwarang_ai_credit_accounts a
        set
            monthly_reserved_credits = v_other_monthly_reserved,
            purchased_reserved_credits = v_other_purchased_reserved,
            updated_at = now()
        where a.user_id = v_request.user_id;

        perform private.sync_hwarang_credit_aggregate(v_request.user_id);

        update public.hwarang_ai_request_registry
        set
            status = 'failed',
            actual_credits = 0,
            actual_monthly_credits = 0,
            actual_purchased_credits = 0,
            completed_at = now()
        where request_id = p_request_id;
    end if;

    -- If the request crossed midnight/month-end, refresh the monthly bucket only
    -- after all old-period monthly reservations have been released.
    perform private.ensure_hwarang_monthly_credit(v_request.user_id);

    select a.balance_credits,a.reserved_credits,
           greatest(0,a.balance_credits-a.reserved_credits)
    into balance_credits,reserved_credits,available_credits
    from public.hwarang_ai_credit_accounts a
    where a.user_id = v_request.user_id;

    return next;
end;
$$;

-- ---------------------------------------------------------
-- 10. Super-admin operational view with effective lazy monthly balance.
-- Dormant users still display the credit they will receive on first use of the
-- current month, without forcing a write for every row in the admin dashboard.
-- ---------------------------------------------------------
drop view if exists public.hwarang_admin_user_operations_view;

create view public.hwarang_admin_user_operations_view
with (security_invoker = true)
as
with context as (
    select
        private.hwarang_credit_period() as current_period,
        cp.monthly_free_credits,
        cp.remaining_warning_percent
    from public.hwarang_credit_policy cp
    where cp.config_id = 1
)
select
    p.*,
    recent_session.last_seen_at as recent_seen_at,
    recent_session.status as recent_session_status,
    recent_activity.event_code as recent_activity_code,
    recent_activity.feature_code as recent_feature_code,
    recent_activity.created_at as recent_activity_at,

    case
        when ca.user_id is null then ctx.current_period
        when ca.monthly_period < ctx.current_period
         and ca.monthly_reserved_credits = 0
        then ctx.current_period
        else ca.monthly_period
    end as training_credit_period,

    case
        when ca.user_id is null then ctx.monthly_free_credits
        when ca.monthly_period < ctx.current_period
         and ca.monthly_reserved_credits = 0
        then ctx.monthly_free_credits
        else coalesce(ca.monthly_grant_credits,0)
    end as monthly_grant_credits,

    case
        when ca.user_id is null then ctx.monthly_free_credits
        when ca.monthly_period < ctx.current_period
         and ca.monthly_reserved_credits = 0
        then ctx.monthly_free_credits
        else coalesce(ca.monthly_balance_credits,0)
    end as monthly_balance_credits,

    case
        when ca.user_id is null then 0::bigint
        when ca.monthly_period < ctx.current_period
         and ca.monthly_reserved_credits = 0
        then 0::bigint
        else coalesce(ca.monthly_reserved_credits,0)
    end as monthly_reserved_credits,

    coalesce(ca.purchased_balance_credits,0) as purchased_balance_credits,
    coalesce(ca.purchased_reserved_credits,0) as purchased_reserved_credits,

    (
        case
            when ca.user_id is null then ctx.monthly_free_credits
            when ca.monthly_period < ctx.current_period
             and ca.monthly_reserved_credits = 0
            then ctx.monthly_free_credits
            else greatest(0::bigint, coalesce(ca.monthly_balance_credits,0) - coalesce(ca.monthly_reserved_credits,0))
        end
        + greatest(0::bigint, coalesce(ca.purchased_balance_credits,0) - coalesce(ca.purchased_reserved_credits,0))
    ) as training_credit_available,

    floor(
        (case
            when ca.user_id is null then ctx.monthly_free_credits
            when ca.monthly_period < ctx.current_period
             and ca.monthly_reserved_credits = 0
            then ctx.monthly_free_credits
            else coalesce(ca.monthly_grant_credits,0)
         end)
        * ctx.remaining_warning_percent / 100.0
    )::bigint as training_warning_threshold,

    coalesce(va.allocation_seconds,0) as voice_allocation_seconds,
    coalesce(va.balance_seconds,0) as voice_balance_seconds,
    coalesce(va.reserved_seconds,0) as voice_reserved_seconds
from public.profiles_admin_view p
cross join context ctx
left join lateral (
    select s.last_seen_at, s.status
    from public.hwarang_user_sessions s
    where s.user_id = p.user_id
    order by s.last_seen_at desc
    limit 1
) recent_session on true
left join lateral (
    select a.event_code, a.feature_code, a.created_at
    from public.hwarang_activity_log a
    where a.user_id = p.user_id
    order by a.created_at desc
    limit 1
) recent_activity on true
left join public.hwarang_ai_credit_accounts ca
    on ca.user_id = p.user_id
left join public.hwarang_voice_accounts va
    on va.user_id = p.user_id;

revoke all on table public.hwarang_admin_user_operations_view from anon,authenticated;
grant select on table public.hwarang_admin_user_operations_view to service_role;

-- ---------------------------------------------------------
-- 11. RLS / grants for policy and new columns.
-- ---------------------------------------------------------
alter table public.hwarang_credit_policy enable row level security;
revoke all on table public.hwarang_credit_policy from anon,authenticated;
grant select,insert,update,delete on table public.hwarang_credit_policy to service_role;

-- Existing service-role grants on credit/request/ledger tables cover new cols.

-- Refresh execute grants for replaced functions.
revoke all on function public.reserve_hwarang_ai_request(uuid,uuid,integer,text,text,text,bigint)
from public,anon,authenticated;
revoke all on function public.finalize_hwarang_ai_request(uuid,text,bigint)
from public,anon,authenticated;

grant execute on function public.reserve_hwarang_ai_request(uuid,uuid,integer,text,text,text,bigint)
to service_role;
grant execute on function public.finalize_hwarang_ai_request(uuid,text,bigint)
to service_role;

commit;
