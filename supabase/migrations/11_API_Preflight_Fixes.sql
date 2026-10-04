-- =========================================================
-- HWARANG PLATFORM
-- 11 API PREFLIGHT FIXES v1
--
-- Apply ONCE after 10_Pre_API_Finalization.sql.
-- No OpenAI key is required.
--
-- Fixes before paid API connection:
-- - atomic one-user / one-AI-session enforcement
-- - reservation-time session ownership/status validation
-- - Voice reservation expiry aligned with the allowed Voice duration
-- - blocked quota/session attempts persist instead of rolling back with exceptions
-- - duplicate idempotency races cannot double-reserve usage
-- - request processing/retry keeps the original reservation
-- - formal AI assessment snapshot reuse is DB-enforced
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 1. DB-enforced assessment reuse.
-- Identical AI/hybrid assessments for the same immutable snapshot are unique.
-- ---------------------------------------------------------
create unique index if not exists academy_assessments_ai_snapshot_unique_idx
on public.academy_assessments(
    session_id,
    framework_version,
    source_snapshot_hash,
    evaluator_type
)
where source_snapshot_hash is not null
  and evaluator_type in ('ai','hybrid');

-- ---------------------------------------------------------
-- 2. Atomic active-session claim helper.
-- Advisory xact lock serializes claims for the same user, closing the race that
-- existed when two different sessions were started at nearly the same time.
-- Returns NULL on success or a stable block reason on an expected denial.
-- ---------------------------------------------------------
create or replace function private.claim_hwarang_ai_session(
    p_user_id uuid,
    p_academy_session_id uuid,
    p_ttl_seconds integer default 1200
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_existing_session uuid;
    v_ttl integer;
begin
    if p_user_id is null then
        return 'invalid_user';
    end if;

    if p_academy_session_id is null then
        return 'session_required';
    end if;

    v_ttl := greatest(60, least(coalesce(p_ttl_seconds,1200), 7200));

    -- Serialize only claims for this user. Hash collisions merely over-serialize;
    -- they cannot weaken correctness.
    perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));

    delete from public.hwarang_ai_session_locks
    where user_id = p_user_id
      and expires_at < now();

    if not exists (
        select 1
        from public.academy_sessions s
        where s.id = p_academy_session_id
          and s.user_id = p_user_id
          and s.status = 'in_progress'
    ) then
        return 'invalid_or_closed_session';
    end if;

    select academy_session_id
    into v_existing_session
    from public.hwarang_ai_session_locks
    where user_id = p_user_id;

    if found and v_existing_session <> p_academy_session_id then
        return 'active_session_exists';
    end if;

    insert into public.hwarang_ai_session_locks(
        user_id,
        academy_session_id,
        acquired_at,
        last_seen_at,
        expires_at
    )
    values (
        p_user_id,
        p_academy_session_id,
        now(),
        now(),
        now() + make_interval(secs => v_ttl::double precision)
    )
    on conflict (user_id) do update
    set academy_session_id = excluded.academy_session_id,
        last_seen_at = now(),
        expires_at = now() + make_interval(secs => v_ttl::double precision)
    where public.hwarang_ai_session_locks.academy_session_id = excluded.academy_session_id;

    return null;
end;
$$;

revoke all on function private.claim_hwarang_ai_session(uuid,uuid,integer) from public;

-- Keep the public acquire API, but make the claim itself atomic.
create or replace function public.acquire_hwarang_ai_session(
    p_user_id uuid,
    p_academy_session_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_reason text;
begin
    v_reason := private.claim_hwarang_ai_session(
        p_user_id,
        p_academy_session_id,
        1200
    );

    if v_reason is not null then
        raise exception '%', upper(v_reason);
    end if;
end;
$$;

-- Heartbeat the session lock and any in-flight Voice reservation.  Voice gets
-- an initial full-duration expiry as well, so the heartbeat is a second layer,
-- not the only protection against an early prune.
create or replace function public.heartbeat_hwarang_ai_session(
    p_user_id uuid,
    p_academy_session_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    update public.hwarang_ai_session_locks
    set last_seen_at = now(),
        expires_at = greatest(expires_at, now() + interval '20 minutes')
    where user_id = p_user_id
      and academy_session_id = p_academy_session_id
      and expires_at >= now();

    if not found then
        raise exception 'AI_SESSION_LOCK_NOT_FOUND';
    end if;

    update public.hwarang_ai_request_registry
    set expires_at = greatest(expires_at, now() + interval '10 minutes')
    where user_id = p_user_id
      and academy_session_id = p_academy_session_id
      and billing_bucket = 'VOICE'
      and status in ('reserved','processing');
end;
$$;

-- ---------------------------------------------------------
-- 3. Persistent blocked-attempt helper.
-- Expected user-facing denials are returned as status='blocked' rather than
-- raised after INSERT, because raising would roll back both the registry row
-- and the activity log in PostgreSQL.
-- ---------------------------------------------------------
create or replace function private.register_hwarang_ai_block(
    p_user_id uuid,
    p_academy_session_id uuid,
    p_turn_no integer,
    p_purpose text,
    p_interaction_mode text,
    p_billing_bucket text,
    p_idempotency_key text,
    p_reason text,
    p_feature_code text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_request_id uuid;
    v_inserted boolean := false;
begin
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
        actual_credits,
        actual_voice_seconds,
        block_reason,
        completed_at,
        expires_at
    )
    values (
        btrim(p_idempotency_key),
        p_user_id,
        p_academy_session_id,
        p_turn_no,
        p_purpose,
        p_interaction_mode,
        p_billing_bucket,
        'blocked',
        0,
        0,
        0,
        0,
        p_reason,
        now(),
        now() + interval '1 hour'
    )
    on conflict (idempotency_key) do nothing
    returning request_id into v_request_id;

    if v_request_id is not null then
        v_inserted := true;
    else
        select request_id
        into v_request_id
        from public.hwarang_ai_request_registry
        where idempotency_key = btrim(p_idempotency_key)
          and user_id = p_user_id;

        if v_request_id is null then
            raise exception 'IDEMPOTENCY_KEY_CONFLICT';
        end if;
    end if;

    if v_inserted then
        insert into public.hwarang_activity_log(
            user_id,
            app_code,
            event_code,
            feature_code,
            outcome,
            metadata
        )
        values (
            p_user_id,
            'academy',
            'AI_REQUEST_BLOCKED',
            p_feature_code,
            'blocked',
            jsonb_build_object(
                'reason', p_reason,
                'purpose', p_purpose,
                'session_id', p_academy_session_id
            )
        );
    end if;

    return v_request_id;
end;
$$;

revoke all on function private.register_hwarang_ai_block(
    uuid,uuid,integer,text,text,text,text,text,text
) from public;

-- ---------------------------------------------------------
-- 4. TEXT / COACH / EVALUATOR reservation.
-- - expected credit/session denials return a persistent blocked row
-- - session lock is enforced at the same DB boundary as the reservation
-- - idempotency race cannot double-reserve credits
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
begin
    perform private.prune_hwarang_ai_reservations();

    if p_purpose not in ('CUSTOMER','COACH','EVALUATOR') then
        if p_purpose = 'VOICE' then
            raise exception 'VOICE_USE_SEPARATE_ALLOWANCE';
        end if;
        raise exception 'INVALID_AI_PURPOSE';
    end if;

    if p_interaction_mode <> 'TEXT' then
        raise exception 'TEXT_RESERVATION_REQUIRES_TEXT_MODE';
    end if;

    if p_estimated_credits <= 0 then
        raise exception 'INVALID_CREDIT_ESTIMATE';
    end if;

    if p_idempotency_key is null
       or btrim(p_idempotency_key) = ''
       or char_length(p_idempotency_key) > 180 then
        raise exception 'INVALID_IDEMPOTENCY_KEY';
    end if;

    -- Fast duplicate path.
    select *
    into v_request
    from public.hwarang_ai_request_registry
    where idempotency_key = btrim(p_idempotency_key);

    if found then
        if v_request.user_id <> p_user_id then
            raise exception 'IDEMPOTENCY_KEY_CONFLICT';
        end if;

        select greatest(0, balance_credits - reserved_credits)
        into available_credits
        from public.hwarang_ai_credit_accounts
        where user_id = p_user_id;

        request_id := v_request.request_id;
        request_status := v_request.status;
        duplicate := true;
        available_credits := coalesce(available_credits, 0);
        return next;
        return;
    end if;

    if not exists (
        select 1
        from public.profiles
        where id = p_user_id
          and is_active = true
    ) then
        raise exception 'INACTIVE_USER';
    end if;

    select *
    into v_config
    from public.hwarang_ai_runtime_config
    where config_id = 1;

    if not v_config.service_enabled then
        raise exception 'AI_SERVICE_DISABLED';
    end if;

    if not v_config.text_enabled then
        raise exception 'AI_TEXT_DISABLED';
    end if;

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
        select 1
        from public.academy_sessions s
        where s.id = p_academy_session_id
          and s.user_id = p_user_id
          and s.status = 'in_progress'
    ) then
        raise exception 'ACADEMY_SESSION_INVALID_OR_CLOSED';
    end if;

    insert into public.hwarang_ai_credit_accounts(user_id)
    values (p_user_id)
    on conflict (user_id) do nothing;

    select *
    into v_account
    from public.hwarang_ai_credit_accounts
    where user_id = p_user_id
    for update;

    if (v_account.balance_credits - v_account.reserved_credits) < p_estimated_credits then
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
        available_credits := greatest(
            0,
            v_account.balance_credits - v_account.reserved_credits
        );
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
        available_credits := greatest(
            0,
            v_account.balance_credits - v_account.reserved_credits
        );
        return next;
        return;
    end if;

    -- Use ON CONFLICT to close the tiny race between the initial duplicate read
    -- and the INSERT itself.  Credits are reserved only if this transaction
    -- actually created the request row.
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
        now() + interval '10 minutes'
    )
    on conflict (idempotency_key) do nothing
    returning * into v_request;

    if not found then
        select *
        into v_request
        from public.hwarang_ai_request_registry
        where idempotency_key = btrim(p_idempotency_key);

        if v_request.user_id <> p_user_id then
            raise exception 'IDEMPOTENCY_KEY_CONFLICT';
        end if;

        request_id := v_request.request_id;
        request_status := v_request.status;
        duplicate := true;
        available_credits := greatest(
            0,
            v_account.balance_credits - v_account.reserved_credits
        );
        return next;
        return;
    end if;

    update public.hwarang_ai_credit_accounts
    set reserved_credits = reserved_credits + p_estimated_credits,
        updated_at = now()
    where user_id = p_user_id
    returning * into v_account;

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
-- 5. VOICE reservation.
-- Initial expiry covers the entire permitted Voice duration + 10 minute buffer.
-- ---------------------------------------------------------
create or replace function public.reserve_hwarang_voice_request(
    p_user_id uuid,
    p_academy_session_id uuid,
    p_turn_no integer,
    p_idempotency_key text,
    p_requested_seconds bigint
)
returns table(
    request_id uuid,
    request_status text,
    duplicate boolean,
    allowed_voice_seconds bigint,
    available_voice_seconds bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_config public.hwarang_ai_runtime_config%rowtype;
    v_account public.hwarang_voice_accounts%rowtype;
    v_request public.hwarang_ai_request_registry%rowtype;
    v_permissions text[];
    v_hard_minutes numeric;
    v_hard_seconds bigint;
    v_allowed bigint;
    v_lock_reason text;
    v_block_id uuid;
begin
    perform private.prune_hwarang_ai_reservations();

    if p_requested_seconds <= 0 then
        raise exception 'INVALID_VOICE_SECONDS';
    end if;

    if p_idempotency_key is null
       or btrim(p_idempotency_key) = ''
       or char_length(p_idempotency_key) > 180 then
        raise exception 'INVALID_IDEMPOTENCY_KEY';
    end if;

    select *
    into v_request
    from public.hwarang_ai_request_registry
    where idempotency_key = btrim(p_idempotency_key);

    if found then
        if v_request.user_id <> p_user_id then
            raise exception 'IDEMPOTENCY_KEY_CONFLICT';
        end if;

        select greatest(0, balance_seconds - reserved_seconds)
        into available_voice_seconds
        from public.hwarang_voice_accounts
        where user_id = p_user_id;

        request_id := v_request.request_id;
        request_status := v_request.status;
        duplicate := true;
        allowed_voice_seconds := v_request.reserved_voice_seconds;
        available_voice_seconds := coalesce(available_voice_seconds,0);
        return next;
        return;
    end if;

    if not exists (
        select 1
        from public.profiles
        where id = p_user_id
          and is_active = true
    ) then
        raise exception 'INACTIVE_USER';
    end if;

    select *
    into v_config
    from public.hwarang_ai_runtime_config
    where config_id = 1;

    if not v_config.service_enabled then
        raise exception 'AI_SERVICE_DISABLED';
    end if;

    if not v_config.voice_enabled then
        raise exception 'AI_VOICE_DISABLED';
    end if;

    select array_agg(permission_code)
    into v_permissions
    from public.get_hwarang_effective_permissions(p_user_id);

    if not ('academy.simulator' = any(coalesce(v_permissions,array[]::text[]))) then
        raise exception 'AI_SIMULATOR_PERMISSION_REQUIRED';
    end if;

    if not ('academy.voice_simulator' = any(coalesce(v_permissions,array[]::text[]))) then
        raise exception 'AI_VOICE_PERMISSION_REQUIRED';
    end if;

    if not exists (
        select 1
        from public.academy_sessions s
        where s.id = p_academy_session_id
          and s.user_id = p_user_id
          and s.status = 'in_progress'
    ) then
        raise exception 'ACADEMY_SESSION_INVALID_OR_CLOSED';
    end if;

    insert into public.hwarang_voice_accounts(user_id)
    values (p_user_id)
    on conflict (user_id) do nothing;

    select *
    into v_account
    from public.hwarang_voice_accounts
    where user_id = p_user_id
    for update;

    select hard_limit
    into v_hard_minutes
    from public.hwarang_ai_limit_policies
    where scope_type = 'app'
      and scope_key = 'academy.voice'
      and metric = 'voice_minutes'
      and is_enabled = true
    limit 1;

    v_hard_seconds := greatest(
        60::bigint,
        floor(coalesce(v_hard_minutes,30) * 60)::bigint
    );

    v_allowed := least(
        p_requested_seconds,
        v_hard_seconds,
        greatest(0::bigint, v_account.balance_seconds - v_account.reserved_seconds)
    );

    if v_allowed <= 0 then
        v_block_id := private.register_hwarang_ai_block(
            p_user_id,
            p_academy_session_id,
            p_turn_no,
            'VOICE',
            'VOICE',
            'VOICE',
            p_idempotency_key,
            'voice_allowance_exhausted',
            'academy.voice_simulator'
        );

        request_id := v_block_id;
        request_status := 'blocked';
        duplicate := false;
        allowed_voice_seconds := 0;
        available_voice_seconds := greatest(
            0,
            v_account.balance_seconds - v_account.reserved_seconds
        );
        return next;
        return;
    end if;

    v_lock_reason := private.claim_hwarang_ai_session(
        p_user_id,
        p_academy_session_id,
        least(2400, greatest(1200, (v_allowed + 600)::integer))
    );

    if v_lock_reason is not null then
        v_block_id := private.register_hwarang_ai_block(
            p_user_id,
            p_academy_session_id,
            p_turn_no,
            'VOICE',
            'VOICE',
            'VOICE',
            p_idempotency_key,
            v_lock_reason,
            'academy.voice_simulator'
        );

        request_id := v_block_id;
        request_status := 'blocked';
        duplicate := false;
        allowed_voice_seconds := 0;
        available_voice_seconds := greatest(
            0,
            v_account.balance_seconds - v_account.reserved_seconds
        );
        return next;
        return;
    end if;

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
        expires_at
    )
    values (
        btrim(p_idempotency_key),
        p_user_id,
        p_academy_session_id,
        p_turn_no,
        'VOICE',
        'VOICE',
        'VOICE',
        'reserved',
        0,
        v_allowed,
        now() + make_interval(secs => (v_allowed + 600)::double precision)
    )
    on conflict (idempotency_key) do nothing
    returning * into v_request;

    if not found then
        select *
        into v_request
        from public.hwarang_ai_request_registry
        where idempotency_key = btrim(p_idempotency_key);

        if v_request.user_id <> p_user_id then
            raise exception 'IDEMPOTENCY_KEY_CONFLICT';
        end if;

        request_id := v_request.request_id;
        request_status := v_request.status;
        duplicate := true;
        allowed_voice_seconds := v_request.reserved_voice_seconds;
        available_voice_seconds := greatest(
            0,
            v_account.balance_seconds - v_account.reserved_seconds
        );
        return next;
        return;
    end if;

    update public.hwarang_voice_accounts
    set reserved_seconds = reserved_seconds + v_allowed,
        updated_at = now()
    where user_id = p_user_id
    returning * into v_account;

    request_id := v_request.request_id;
    request_status := v_request.status;
    duplicate := false;
    allowed_voice_seconds := v_allowed;
    available_voice_seconds := greatest(
        0,
        v_account.balance_seconds - v_account.reserved_seconds
    );
    return next;
end;
$$;

-- ---------------------------------------------------------
-- 6. Mark a reservation as processing / refresh it for retry.
-- A retry reuses the same request_id + reservation; it must never reserve again.
-- ---------------------------------------------------------
create or replace function public.start_hwarang_ai_request(
    p_request_id uuid,
    p_extend_seconds integer default 600
)
returns table(
    request_status text,
    expires_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_extend integer;
    v_request public.hwarang_ai_request_registry%rowtype;
begin
    v_extend := greatest(60, least(coalesce(p_extend_seconds,600), 3600));

    select *
    into v_request
    from public.hwarang_ai_request_registry
    where request_id = p_request_id
    for update;

    if not found then
        raise exception 'AI_REQUEST_NOT_FOUND';
    end if;

    if v_request.status = 'reserved' then
        update public.hwarang_ai_request_registry as r
        set status = 'processing',
            started_at = coalesce(r.started_at, now()),
            expires_at = greatest(
                r.expires_at,
                now() + make_interval(secs => v_extend::double precision)
            )
        where r.request_id = p_request_id
        returning r.status, r.expires_at
        into request_status, expires_at;
    elsif v_request.status = 'processing' then
        update public.hwarang_ai_request_registry as r
        set expires_at = greatest(
                r.expires_at,
                now() + make_interval(secs => v_extend::double precision)
            )
        where r.request_id = p_request_id
        returning r.status, r.expires_at
        into request_status, expires_at;
    else
        request_status := v_request.status;
        expires_at := v_request.expires_at;
    end if;

    return next;
end;
$$;

-- ---------------------------------------------------------
-- 7. Grants for replaced/new APIs.
-- ---------------------------------------------------------
revoke all on function public.acquire_hwarang_ai_session(uuid,uuid)
from public, anon, authenticated;
revoke all on function public.heartbeat_hwarang_ai_session(uuid,uuid)
from public, anon, authenticated;
revoke all on function public.reserve_hwarang_ai_request(uuid,uuid,integer,text,text,text,bigint)
from public, anon, authenticated;
revoke all on function public.reserve_hwarang_voice_request(uuid,uuid,integer,text,bigint)
from public, anon, authenticated;
revoke all on function public.start_hwarang_ai_request(uuid,integer)
from public, anon, authenticated;

grant execute on function public.acquire_hwarang_ai_session(uuid,uuid)
to service_role;
grant execute on function public.heartbeat_hwarang_ai_session(uuid,uuid)
to service_role;
grant execute on function public.reserve_hwarang_ai_request(uuid,uuid,integer,text,text,text,bigint)
to service_role;
grant execute on function public.reserve_hwarang_voice_request(uuid,uuid,integer,text,bigint)
to service_role;
grant execute on function public.start_hwarang_ai_request(uuid,integer)
to service_role;

commit;
