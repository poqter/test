-- Additive receipt boundary. Existing adjustment functions and ledgers stay intact.
create table if not exists private.hwarang_admin_asset_requests (
    request_id uuid primary key,
    actor_user_id uuid not null,
    payload jsonb not null,
    result jsonb not null,
    created_at timestamptz not null default now()
);
alter table private.hwarang_admin_asset_requests enable row level security;
revoke all on private.hwarang_admin_asset_requests from public, anon, authenticated;
grant usage on schema private to service_role;
grant select, insert on private.hwarang_admin_asset_requests to service_role;

create or replace function public.admin_apply_hwarang_asset_request(
    p_actor_user_id uuid, p_request_id uuid, p_asset text,
    p_target_user_ids uuid[], p_operation text, p_amount bigint,
    p_source_type text, p_note text
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
    v_payload jsonb;
    v_previous private.hwarang_admin_asset_requests%rowtype;
    v_result jsonb;
    v_targets uuid[];
begin
    if not exists (select 1 from public.profiles where id=p_actor_user_id
                   and role='super_admin' and is_active) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;
    if p_request_id is null or p_asset is null or p_asset not in ('training_credit','voice')
       or p_operation is null or p_operation not in ('grant','revoke','reset')
       or p_amount is null or p_amount < 0 or (p_operation <> 'reset' and p_amount=0)
       or p_source_type is null or p_source_type not in ('purchase','promotion_reward','admin_adjustment') then
        raise exception 'INVALID_ASSET_REQUEST';
    end if;
    select array_agg(x order by x) into v_targets
      from (select distinct x from unnest(p_target_user_ids) u(x) where x is not null) q;
    if coalesce(cardinality(v_targets),0)=0 then raise exception 'TARGET_USERS_REQUIRED'; end if;
    v_payload := jsonb_build_object('asset',p_asset,'targets',v_targets,'operation',p_operation,
                                   'amount',p_amount,'source',p_source_type,'note',coalesce(p_note,''));
    -- Same request waits for the first transaction, including concurrent retries.
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_request_id::text,0));
    select * into v_previous from private.hwarang_admin_asset_requests where request_id=p_request_id;
    if found then
        if v_previous.actor_user_id<>p_actor_user_id or v_previous.payload<>v_payload then
            raise exception 'ASSET_REQUEST_CONFLICT';
        end if;
        return v_previous.result;
    end if;
    -- Lock targets in deterministic order to avoid overlapping-batch deadlocks.
    perform 1 from public.profiles where id=any(v_targets) order by id for update;
    if p_asset='voice' then
        v_result := public.admin_bulk_adjust_hwarang_voice_minutes(p_actor_user_id,v_targets,
                      p_operation,p_amount,p_source_type,p_note);
    else
        v_result := public.admin_bulk_adjust_hwarang_purchased_credits(p_actor_user_id,v_targets,
                      p_operation,p_amount,p_source_type,p_note);
    end if;
    v_result := v_result || jsonb_build_object('request_id',p_request_id);
    insert into private.hwarang_admin_asset_requests(request_id,actor_user_id,payload,result)
    values(p_request_id,p_actor_user_id,v_payload,v_result);
    return v_result;
end;
$$;

create or replace function public.admin_get_hwarang_asset_request(p_actor_user_id uuid,p_request_id uuid)
returns jsonb language plpgsql security invoker set search_path = '' as $$
begin
    if not exists (select 1 from public.profiles where id=p_actor_user_id
                   and role='super_admin' and is_active) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;
    return (select result from private.hwarang_admin_asset_requests
            where request_id=p_request_id and actor_user_id=p_actor_user_id);
end;
$$;
revoke all on function public.admin_apply_hwarang_asset_request(uuid,uuid,text,uuid[],text,bigint,text,text) from public,anon,authenticated;
revoke all on function public.admin_get_hwarang_asset_request(uuid,uuid) from public,anon,authenticated;
grant execute on function public.admin_apply_hwarang_asset_request(uuid,uuid,text,uuid[],text,bigint,text,text) to service_role;
grant execute on function public.admin_get_hwarang_asset_request(uuid,uuid) to service_role;
