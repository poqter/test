begin;

create function private.kakao_require_super_admin() returns uuid
language plpgsql stable security definer set search_path = '' as $$
declare actor uuid := private.kakao_require_user();
begin
    if not exists (
        select 1 from public.profiles
        where id = actor and is_active and role = 'super_admin'
    ) then
        raise exception 'Forbidden' using errcode = '42501';
    end if;
    return actor;
end;
$$;

create function private.kakao_super_admin_list() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
    perform private.kakao_require_super_admin();
    return coalesce((
        select jsonb_agg(jsonb_build_object(
            'owner_id', u.id, 'label', u.display_name, 'login_id', u.login_id,
            'connection_status', c.status, 'admin_paused', p.admin_paused,
            'enabled', p.enabled, 'time', to_char(p.delivery_time, 'HH24:MI'),
            'days', p.days, 'send_empty', p.send_empty,
            'weather_region_key', p.weather_region_key, 'updated_at', p.updated_at,
            'test_status', case
                when t.status = 'queued' and t.expires_at <= now() then 'expired'
                when t.status = 'processing' and t.expires_at <= now() then 'uncertain'
                else t.status end,
            'test_at', coalesce(t.completed_at, t.created_at)
        ) order by u.display_name, u.login_id)
        from public.kakao_multi_preferences p
        join public.profiles u on u.id = p.owner_id and u.is_active
        join public.kakao_multi_connections c on c.owner_id = p.owner_id
        left join lateral (
            select status, expires_at, completed_at, created_at
            from public.kakao_multi_test_requests
            where owner_id = p.owner_id order by created_at desc, id desc limit 1
        ) t on true
        where not private.kakao_service_excluded_owner(u.id)
    ), '[]'::jsonb);
end;
$$;

create function private.kakao_super_admin_save(
    p_owner_id uuid, p_expected_updated_at timestamptz, p_enabled boolean,
    p_time text, p_days integer[], p_send_empty boolean, p_region_key text, p_admin_paused boolean
) returns boolean language plpgsql security definer set search_path = '' as $$
declare
    actor uuid := private.kakao_require_super_admin();
    connection public.kakao_multi_connections;
    previous public.kakao_multi_preferences;
    current_settings public.kakao_multi_preferences;
    cancel_reason text;
begin
    if p_expected_updated_at is null or p_enabled is null or p_send_empty is null
        or p_admin_paused is null or p_time is null or p_time !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
        or p_days is null or cardinality(p_days) not between 1 and 7
        or not p_days <@ array[0,1,2,3,4,5,6] or array_position(p_days,null) is not null
        or (p_region_key is not null and not private.kakao_weather_region_valid(p_region_key))
        or (p_enabled and p_region_key is null) then
        raise exception 'Invalid preferences' using errcode = '22023';
    end if;
    select * into connection from public.kakao_multi_connections where owner_id = p_owner_id for update;
    if not found or not private.kakao_service_owner_active(p_owner_id)
        or private.kakao_service_excluded_owner(p_owner_id) then
        raise exception 'Target unavailable' using errcode = '42501';
    end if;
    if p_enabled and (connection.status <> 'connected' or not connection.talk_message_granted) then
        raise exception 'Reconnect required' using errcode = '22023';
    end if;
    select * into previous from public.kakao_multi_preferences where owner_id = p_owner_id for update;
    if not found or previous.updated_at is distinct from p_expected_updated_at then
        return false;
    end if;
    update public.kakao_multi_preferences
    set enabled = p_enabled, delivery_time = p_time::time,
        days = array(select distinct d from unnest(p_days) d order by d),
        send_empty = p_send_empty, weather_region_key = p_region_key,
        admin_paused = p_admin_paused, updated_at = clock_timestamp()
    where owner_id = p_owner_id returning * into current_settings;

    cancel_reason := case
        when not p_enabled or p_admin_paused then 'paused'
        when previous.weather_region_key is distinct from p_region_key then 'scope_changed'
    end;
    if cancel_reason is not null then
        update public.kakao_multi_jobs set status = 'cancelled', outcome = cancel_reason, completed_at = clock_timestamp()
        where owner_id = p_owner_id and status = 'reserved';
        update public.kakao_multi_batches set status = 'cancelled', outcome = cancel_reason, completed_at = clock_timestamp()
        where owner_id = p_owner_id and status in ('reserved','held');
    end if;
    insert into public.hwarang_admin_audit_log(actor_user_id, target_user_id, action, details)
    values (actor, p_owner_id, 'kakao_preferences_updated', jsonb_build_object(
        'before', to_jsonb(previous) - 'owner_id', 'after', to_jsonb(current_settings) - 'owner_id'
    ));
    return true;
end;
$$;

create function private.kakao_super_admin_test(p_owner_id uuid, p_request_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
    actor uuid := private.kakao_require_super_admin();
    result jsonb;
begin
    if private.kakao_service_excluded_owner(p_owner_id) then
        raise exception 'Target unavailable' using errcode = '42501';
    end if;
    result := private.kakao_test_enqueue(p_owner_id, p_request_id);
    if result->>'status' = 'queued' and not coalesce((result->>'reused')::boolean, false) then
        insert into public.hwarang_admin_audit_log(actor_user_id, target_user_id, action, details)
        values (actor, p_owner_id, 'kakao_test_requested', jsonb_build_object('request_id', p_request_id));
    end if;
    return result;
end;
$$;

create function public.kakao_super_admin_list() returns jsonb
language sql stable security invoker set search_path = '' as $$
    select private.kakao_super_admin_list()
$$;
create function public.kakao_super_admin_save(
    p_owner_id uuid, p_expected_updated_at timestamptz, p_enabled boolean,
    p_time text, p_days integer[], p_send_empty boolean, p_region_key text, p_admin_paused boolean
) returns boolean language sql security invoker set search_path = '' as $$
    select private.kakao_super_admin_save(p_owner_id, p_expected_updated_at, p_enabled,
        p_time, p_days, p_send_empty, p_region_key, p_admin_paused)
$$;
create function public.kakao_super_admin_test(p_owner_id uuid, p_request_id uuid) returns jsonb
language sql security invoker set search_path = '' as $$
    select private.kakao_super_admin_test(p_owner_id, p_request_id)
$$;

revoke all on function private.kakao_require_super_admin() from public, anon, authenticated;
revoke all on function private.kakao_super_admin_list(), public.kakao_super_admin_list(),
    private.kakao_super_admin_save(uuid,timestamptz,boolean,text,integer[],boolean,text,boolean),
    public.kakao_super_admin_save(uuid,timestamptz,boolean,text,integer[],boolean,text,boolean),
    private.kakao_super_admin_test(uuid,uuid), public.kakao_super_admin_test(uuid,uuid)
    from public, anon, authenticated;
grant execute on function private.kakao_super_admin_list(), public.kakao_super_admin_list(),
    private.kakao_super_admin_save(uuid,timestamptz,boolean,text,integer[],boolean,text,boolean),
    public.kakao_super_admin_save(uuid,timestamptz,boolean,text,integer[],boolean,text,boolean),
    private.kakao_super_admin_test(uuid,uuid), public.kakao_super_admin_test(uuid,uuid)
    to authenticated;

commit;
