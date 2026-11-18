update public.hwarang_ai_runtime_config
set text_enabled = false, voice_enabled = false, assessment_enabled = false
where config_id = 1 and (text_enabled or voice_enabled or assessment_enabled);

-- Suspend only direct client access to legacy learner data. Onboarding, the
-- service role, private helpers and every existing RPC retain their privileges.
revoke select, insert, update on public.academy_cases, public.academy_sessions,
    public.academy_learning_profiles from authenticated;
revoke select, insert on public.academy_assessments from authenticated;

-- The existing briefing reader and reservation RPC both use this same row.
create function public.admin_set_briefing_service_enabled(p_actor uuid, p_expected boolean, p_enabled boolean)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
    if not exists (select 1 from public.profiles where id=p_actor and role='super_admin' and is_active) then
        raise exception 'SUPER_ADMIN_REQUIRED';
    end if;
    if p_enabled is null or p_expected is null then raise exception 'INVALID_BRIEFING_STATE'; end if;
    update public.hwarang_ai_runtime_config
       set service_enabled=p_enabled, updated_at=now(), updated_by=p_actor
     where config_id=1 and service_enabled=p_expected;
    if not found then raise exception 'BRIEFING_STATE_CHANGED'; end if;
    insert into public.hwarang_admin_audit_log(actor_user_id,action,details)
    values(p_actor, 'briefing_service_updated', jsonb_build_object('previous',p_expected,'enabled',p_enabled));
    return p_enabled;
end $$;
revoke all on function public.admin_set_briefing_service_enabled(uuid,boolean,boolean) from public, anon, authenticated;
grant execute on function public.admin_set_briefing_service_enabled(uuid,boolean,boolean) to service_role;
