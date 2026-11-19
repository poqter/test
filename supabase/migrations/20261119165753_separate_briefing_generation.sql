begin;

-- Serialize the initial copy with any in-flight writes to the old switch.
lock table public.hwarang_ai_runtime_config in share mode;
alter table public.hwarang_briefing_operating_policy
    add column if not exists generation_enabled boolean;

do $$
begin
    if not exists (select 1 from public.hwarang_briefing_operating_policy where policy_key = 'WORKSPACE') then
        raise exception 'BRIEFING_POLICY_MISSING';
    end if;
    update public.hwarang_briefing_operating_policy
       set generation_enabled = (select service_enabled from public.hwarang_ai_runtime_config where config_id = 1)
     where policy_key = 'WORKSPACE' and generation_enabled is null;
end $$;
alter table public.hwarang_briefing_operating_policy
    alter column generation_enabled set not null,
    alter column generation_enabled set default false;

create or replace function public.admin_set_briefing_service_enabled(p_actor uuid, p_expected boolean, p_enabled boolean)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
    if not exists (select 1 from public.profiles where id = p_actor and is_active and role = 'super_admin') then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;
    if p_enabled is null or p_expected is null then raise exception 'INVALID_BRIEFING_STATE'; end if;
    update public.hwarang_briefing_operating_policy
       set generation_enabled = p_enabled, updated_at = now()
     where policy_key = 'WORKSPACE' and generation_enabled = p_expected;
    if not found then raise exception 'BRIEFING_STATE_CHANGED'; end if;
    insert into public.hwarang_admin_audit_log(actor_user_id, action, details)
    values (p_actor, 'briefing_service_updated', jsonb_build_object('previous',p_expected,'enabled',p_enabled));
    return p_enabled;
end $$;

create or replace function public.hwarang_reserve_briefing_request(p_date date, p_kind text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare
    budget public.hwarang_briefing_daily_budget;
begin
    perform 1 from public.hwarang_briefing_operating_policy
     where policy_key = 'WORKSPACE' and generation_enabled for share;
    if not found then raise exception 'AI_SERVICE_DISABLED'; end if;

    insert into public.hwarang_briefing_daily_budget(briefing_date) values (p_date) on conflict do nothing;
    select * into budget from public.hwarang_briefing_daily_budget where briefing_date = p_date for update;
    if p_kind = 'web' and budget.web_requests < 6 and budget.search_actions < 6 then
        update public.hwarang_briefing_daily_budget set web_requests = web_requests + 1 where briefing_date = p_date;
        return true;
    elsif p_kind = 'analysis' and budget.analysis_requests < 4 then
        update public.hwarang_briefing_daily_budget set analysis_requests = analysis_requests + 1 where briefing_date = p_date;
        return true;
    end if;
    return false;
end $$;

commit;
