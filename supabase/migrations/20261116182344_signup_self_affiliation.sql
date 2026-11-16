-- Self-service signup and reporting managers. Existing records/roles unchanged.
create function public.signup_affiliation_options(p_code text)
returns table(organization_code text,organization_name text,parent_name text,unit_type text)
language sql stable security definer set search_path='' as $$
 select u.code,u.name,p.name,u.unit_type from public.organization_units u
 left join public.organization_units p on p.id=u.parent_id
 where u.is_active and u.code not in ('PLATFORM_ROOT','PLATFORM_OPERATIONS')
 and (u.unit_type in ('branch','team') or (u.unit_type='head_unit' and u.code in ('DONGVAN_HQ','VISION_HQ','BISANG_HQ')))
 and exists(select 1 from public.hwarang_join_codes j where j.code_hash=private.hash_hwarang_join_code(p_code)
 and j.is_active and j.starts_at<=now() and (j.expires_at is null or j.expires_at>now())
 and (j.max_uses is null or j.used_count<j.max_uses)
 and (j.scope_organization_unit_id is null or j.scope_organization_unit_id=u.id
 or (j.allow_descendants and private.is_org_descendant(j.scope_organization_unit_id,u.id))))
 order by p.sort_order,u.sort_order,u.name
$$;
revoke all on function public.signup_affiliation_options(text) from public,anon,authenticated;
grant execute on function public.signup_affiliation_options(text) to service_role;

create function public.signup_manager_candidates(p_code text,p_organization_code text,p_position_code text)
returns table(id uuid,display_name text,position_code text)
language sql stable security definer set search_path='' as $$
 select p.id,p.display_name,p.position_code from public.profiles p
 join public.organization_units u on u.id=p.organization_unit_id
 join public.signup_affiliation_options(p_code) o on o.organization_code=u.code
 where u.code=p_organization_code and p.is_active
 and p.position_code in ('team_leader','deputy_branch_manager')
 and p_position_code in ('fp','partner','team_leader','deputy_branch_manager','branch_manager','division_head')
 and ((p_position_code='division_head' and o.unit_type='head_unit') or (p_position_code<>'division_head' and o.unit_type in ('branch','team')))
 order by p.display_name,p.id
$$;
revoke all on function public.signup_manager_candidates(text,text,text) from public,anon,authenticated;
grant execute on function public.signup_manager_candidates(text,text,text) to service_role;

create function private.self_reporting_snapshot() returns jsonb
language plpgsql stable security definer set search_path='' as $$
declare subject uuid:=auth.uid();result jsonb;
begin
 if subject is null or not exists(select 1 from public.profiles where id=subject and is_active) then raise exception 'ACCOUNT_REQUIRED';end if;
 select jsonb_build_object('team_leader',(select leader from public.sales_team_assignments where member=subject),
 'deputy_manager',(select leader from public.sales_deputy_assignments where member=subject),
 'candidates',coalesce((select jsonb_agg(jsonb_build_object('id',p.id,'display_name',p.display_name,'position_code',p.position_code) order by p.display_name,p.id)
 from public.profiles p join public.profiles me on me.id=subject and me.organization_unit_id=p.organization_unit_id
 join public.organization_units u on u.id=me.organization_unit_id and u.is_active
 where p.is_active and p.id<>subject and p.position_code in ('team_leader','deputy_branch_manager')
 and not exists(with recursive edges as(select member,leader from public.sales_team_assignments union select member,leader from public.sales_deputy_assignments),
 chain(id) as(select p.id union select e.leader from edges e join chain c on e.member=c.id)
 select 1 from chain where id=subject)), '[]'::jsonb)) into result;
 return result;
end $$;
revoke all on function private.self_reporting_snapshot() from public,anon;
grant execute on function private.self_reporting_snapshot() to authenticated;
create function public.get_reporting_managers() returns jsonb language sql stable security invoker set search_path='' as $$ select private.self_reporting_snapshot() $$;
revoke all on function public.get_reporting_managers() from public,anon;
grant execute on function public.get_reporting_managers() to authenticated;

create function private.self_set_reporting_managers(p_team_leader uuid,p_deputy_manager uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare subject uuid:=auth.uid();old_team uuid;old_deputy uuid;candidate jsonb;
begin
 perform pg_advisory_xact_lock(hashtextextended('sales-reporting-manager-assignments',0));
 if subject is null or not exists(select 1 from public.profiles p join public.organization_units u on u.id=p.organization_unit_id where p.id=subject and p.is_active and u.is_active) then raise exception 'ACCOUNT_REQUIRED';end if;
 -- Lock the actor and selected profiles so organization/position cannot change mid-save.
 perform 1 from public.profiles where id in (subject,p_team_leader,p_deputy_manager) order by id for update;
 candidate:=private.self_reporting_snapshot();
 if p_team_leader is not null and not exists(select 1 from jsonb_array_elements(candidate->'candidates') c where c->>'id'=p_team_leader::text and c->>'position_code'='team_leader') then raise exception 'INVALID_TEAM_LEADER';end if;
 if p_deputy_manager is not null and not exists(select 1 from jsonb_array_elements(candidate->'candidates') c where c->>'id'=p_deputy_manager::text and c->>'position_code'='deputy_branch_manager') then raise exception 'INVALID_DEPUTY_MANAGER';end if;
 select leader into old_team from public.sales_team_assignments where member=subject;
 select leader into old_deputy from public.sales_deputy_assignments where member=subject;
 delete from public.sales_team_assignments where member=subject;
 delete from public.sales_deputy_assignments where member=subject;
 if p_team_leader is not null then insert into public.sales_team_assignments(member,leader) values(subject,p_team_leader);end if;
 if p_deputy_manager is not null then insert into public.sales_deputy_assignments(member,leader) values(subject,p_deputy_manager);end if;
 insert into public.hwarang_admin_audit_log(actor_user_id,target_user_id,action,details) values(subject,subject,'self_reporting_managers_updated',jsonb_build_object('old_team_leader',old_team,'team_leader',p_team_leader,'old_deputy_manager',old_deputy,'deputy_manager',p_deputy_manager));
 return private.self_reporting_snapshot();
end $$;
revoke all on function private.self_set_reporting_managers(uuid,uuid) from public,anon;
grant execute on function private.self_set_reporting_managers(uuid,uuid) to authenticated;
create function public.set_reporting_managers(p_team_leader uuid,p_deputy_manager uuid) returns jsonb language sql security invoker set search_path='' as $$ select private.self_set_reporting_managers(p_team_leader,p_deputy_manager) $$;
revoke all on function public.set_reporting_managers(uuid,uuid) from public,anon;
grant execute on function public.set_reporting_managers(uuid,uuid) to authenticated;

create or replace function private.handle_new_hwarang_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_mode text;

    v_login_id text;
    v_display_name text;
    v_org_code text;
    v_join_code text;

    v_org_id uuid;
    v_position text;
    v_team uuid;
    v_deputy uuid;
    v_join public.hwarang_join_codes%rowtype;
begin
    v_mode := coalesce(new.raw_user_meta_data ->> 'signup_mode', '');

    if v_mode <> 'hwarang_self_signup' then
        insert into public.profiles (
            id,
            auth_email,
            role,
            is_active,
            position_code
        )
        values (
            new.id,
            lower(new.email),
            'user',
            false,
            'fp'
        )
        on conflict (id) do nothing;

        return new;
    end if;

    v_login_id :=
        nullif(btrim(new.raw_user_meta_data ->> 'login_id'), '');

    v_display_name :=
        nullif(btrim(new.raw_user_meta_data ->> 'display_name'), '');

    v_org_code :=
        nullif(btrim(new.raw_user_meta_data ->> 'organization_code'), '');

    v_join_code :=
        nullif(btrim(new.raw_user_meta_data ->> 'join_code'), '');

    if v_login_id is null then
        raise exception 'LOGIN_ID_REQUIRED';
    end if;

    if v_display_name is null then
        raise exception 'DISPLAY_NAME_REQUIRED';
    end if;

    if v_org_code is null then
        raise exception 'ORGANIZATION_REQUIRED';
    end if;

    if v_join_code is null then
        raise exception 'JOIN_CODE_REQUIRED';
    end if;

    if v_login_id !~ '^[A-Za-z0-9._-]{3,32}$' then
        raise exception 'INVALID_LOGIN_ID';
    end if;

    v_position := coalesce(nullif(btrim(new.raw_user_meta_data ->> 'position_code'), ''), 'fp');
    if v_position not in ('fp','partner','team_leader','deputy_branch_manager','branch_manager','division_head') then raise exception 'INVALID_POSITION'; end if;
    v_team := nullif(new.raw_user_meta_data ->> 'team_leader','')::uuid;
    v_deputy := nullif(new.raw_user_meta_data ->> 'deputy_manager','')::uuid;

    select id
    into v_org_id
    from public.organization_units
    where code = v_org_code
      and ((v_position='division_head' and unit_type='head_unit' and code in ('DONGVAN_HQ','VISION_HQ','BISANG_HQ'))
        or (v_position<>'division_head' and unit_type in ('branch','team')))
      and code not in ('PLATFORM_ROOT','PLATFORM_OPERATIONS')
      and is_active = true;

    if v_org_id is null then
        raise exception 'INVALID_ORGANIZATION';
    end if;

    select *
    into v_join
    from public.hwarang_join_codes
    where code_hash = private.hash_hwarang_join_code(v_join_code)
      and is_active = true
      and starts_at <= now()
      and (expires_at is null or expires_at > now())
      and (max_uses is null or used_count < max_uses)
    limit 1
    for update;

    if not found then
        raise exception 'INVALID_JOIN_CODE';
    end if;

    if v_join.scope_organization_unit_id is not null then
        if v_join.allow_descendants = true then
            if not private.is_org_descendant(
                v_join.scope_organization_unit_id,
                v_org_id
            ) then
                raise exception 'ORGANIZATION_NOT_ALLOWED';
            end if;
        else
            if v_join.scope_organization_unit_id <> v_org_id then
                raise exception 'ORGANIZATION_NOT_ALLOWED';
            end if;
        end if;
    end if;

    insert into public.profiles (
        id,
        login_id,
        auth_email,
        display_name,
        role,
        is_active,
        organization_unit_id,
        position_code
    )
    values (
        new.id,
        v_login_id,
        lower(new.email),
        v_display_name,
        'user',
        true,
        v_org_id,
        v_position
    );

    if v_team is not null then insert into public.sales_team_assignments(member,leader) values(new.id,v_team); end if;
    if v_deputy is not null then insert into public.sales_deputy_assignments(member,leader) values(new.id,v_deputy); end if;

    update public.hwarang_join_codes
    set used_count = used_count + 1
    where id = v_join.id;

    -- 가입코드 원문을 Auth metadata에 남기지 않음
    update auth.users
    set raw_user_meta_data =
        coalesce(raw_user_meta_data, '{}'::jsonb) - 'join_code'
    where id = new.id;

    return new;

exception
    when unique_violation then
        raise exception 'LOGIN_ID_ALREADY_EXISTS';
end;
$$;

revoke all on function private.handle_new_hwarang_user()
    from public, anon, authenticated;


