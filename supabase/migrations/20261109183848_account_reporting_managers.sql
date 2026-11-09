-- Optional reporting managers share the existing team assignments, preserving links.
create table public.sales_deputy_assignments (
 member uuid primary key references public.profiles(id),
 leader uuid not null references public.profiles(id), check(member<>leader));
create index sales_deputy_leader on public.sales_deputy_assignments(leader);
create index if not exists sales_team_leader on public.sales_team_assignments(leader);
alter table public.sales_deputy_assignments enable row level security;
revoke all on public.sales_deputy_assignments from public,anon,authenticated;
grant select on public.sales_deputy_assignments to authenticated;
grant all on public.sales_deputy_assignments to service_role;
grant all on public.sales_team_assignments to service_role;

create function private.sales_validate_assignment() returns trigger language plpgsql security definer set search_path='' as $$
declare expected text;
begin
 perform pg_advisory_xact_lock(hashtextextended('sales-reporting-manager-assignments',0));
 expected:=case when tg_table_name='sales_team_assignments' then 'team_leader' else 'deputy_branch_manager' end;
 if new.member=new.leader or not exists(select 1 from public.profiles m join public.profiles l on m.organization_unit_id=l.organization_unit_id
 where m.id=new.member and l.id=new.leader and l.is_active and l.position_code=expected)
 then raise exception '같은 직할·지점의 활성 담당자만 지정할 수 있습니다';end if;
 if exists(with recursive edges as(select member,leader from public.sales_team_assignments union select member,leader from public.sales_deputy_assignments),
 chain(id) as(select new.leader union select e.leader from edges e join chain c on e.member=c.id)
 select 1 from chain where id=new.member) then raise exception '담당자 연결이 순환할 수 없습니다';end if;
 return new;
end $$;
revoke all on function private.sales_validate_assignment() from public,anon,authenticated;
create trigger validate_team_assignment before insert or update on public.sales_team_assignments for each row execute function private.sales_validate_assignment();
create trigger validate_deputy_assignment before insert or update on public.sales_deputy_assignments for each row execute function private.sales_validate_assignment();

create or replace function private.sales_scope_for(subject uuid,preview boolean) returns table(member uuid,label text,unit uuid,managed boolean)
language sql stable security definer set search_path='' as $$
 with recursive me as (select * from public.profiles where id=subject and is_active and private.sales_enabled() and (subject=auth.uid() or private.sales_admin())),
 tree(id) as (select organization_unit_id from me union select u.id from public.organization_units u join tree on u.parent_id=tree.id where u.is_active),
 valid_team as (select a.* from public.sales_team_assignments a join public.profiles l on l.id=a.leader join public.profiles m on m.id=a.member
 where l.is_active and l.position_code='team_leader' and l.organization_unit_id=m.organization_unit_id),
 valid_deputy as (select a.* from public.sales_deputy_assignments a join public.profiles l on l.id=a.leader join public.profiles m on m.id=a.member
 where l.is_active and l.position_code='deputy_branch_manager' and l.organization_unit_id=m.organization_unit_id),
 members as (select p.*,((me.role='super_admin' and not preview) or
 (me.position_code in ('branch_manager','division_head','chief_representative') and p.organization_unit_id in(select id from tree)) or
 (me.position_code='team_leader' and p.organization_unit_id=me.organization_unit_id and (p.id=subject or exists(select 1 from valid_team a where a.leader=subject and a.member=p.id))) or
 (me.position_code='deputy_branch_manager' and p.organization_unit_id=me.organization_unit_id and
 (p.id=subject or exists(select 1 from valid_deputy a where a.leader=subject and a.member=p.id) or
 exists(select 1 from valid_team t join valid_deputy d on d.member=t.leader where d.leader=subject and t.member=p.id)))) as managed
 from me cross join public.profiles p where p.is_active)
 select id,display_name,organization_unit_id,managed from members where id=subject or managed
$$;
-- All reads are restricted to the same scope used by calendar and reports.
create policy team_scope_read on public.sales_team_assignments for select to authenticated
 using(private.sales_enabled() and member in(select s.member from private.sales_scope() s));
create policy deputy_scope_read on public.sales_deputy_assignments for select to authenticated
 using(private.sales_enabled() and member in(select s.member from private.sales_scope() s));

-- Server-only account operation: account fields and both optional links commit together.
create function public.admin_apply_hwarang_user_with_managers(
 p_actor_user_id uuid,p_target_user_id uuid,p_display_name text,p_role text,p_is_active boolean,
 p_organization_unit_id uuid,p_position_code text,p_app_access jsonb,p_permissions jsonb,
 p_team_leader uuid,p_deputy_manager uuid) returns void
language plpgsql security invoker set search_path='' as $$
declare old_team uuid;old_deputy uuid;
begin
 perform pg_advisory_xact_lock(hashtextextended('sales-reporting-manager-assignments',0));
 select leader into old_team from public.sales_team_assignments where member=p_target_user_id;
 select leader into old_deputy from public.sales_deputy_assignments where member=p_target_user_id;
 perform public.admin_apply_hwarang_user(p_actor_user_id,p_target_user_id,p_display_name,p_role,p_is_active,p_organization_unit_id,p_position_code,p_app_access,p_permissions);
 delete from public.sales_team_assignments where member=p_target_user_id;
 delete from public.sales_deputy_assignments where member=p_target_user_id;
 if p_team_leader is not null then insert into public.sales_team_assignments(member,leader) values(p_target_user_id,p_team_leader);end if;
 if p_deputy_manager is not null then insert into public.sales_deputy_assignments(member,leader) values(p_target_user_id,p_deputy_manager);end if;
 insert into public.hwarang_admin_audit_log(actor_user_id,target_user_id,action,details)
 values(p_actor_user_id,p_target_user_id,'reporting_managers_updated',jsonb_build_object('old_team_leader',old_team,'team_leader',p_team_leader,'old_deputy_manager',old_deputy,'deputy_manager',p_deputy_manager));
end $$;
revoke all on function public.admin_apply_hwarang_user_with_managers(uuid,uuid,text,text,boolean,uuid,text,jsonb,jsonb,uuid,uuid) from public,anon,authenticated;
grant execute on function public.admin_apply_hwarang_user_with_managers(uuid,uuid,text,text,boolean,uuid,text,jsonb,jsonb,uuid,uuid) to service_role;

create or replace function private.sales_scope()
returns table(member uuid,label text,unit uuid,managed boolean)
language plpgsql stable security definer set search_path='' as $$
declare selection jsonb; manager boolean;
begin
 selection:=private.sales_view_selection();
 if selection is null then
  return query select * from private.sales_scope_for(auth.uid(),
   coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-hwarang-view-scope','all') <> 'all');
  return;
 end if;
 manager:=selection->>'position' in ('chief_representative','division_head','branch_manager','deputy_branch_manager','team_leader','platform_administrator');
 if selection->>'position' in ('chief_representative','division_head','branch_manager') then
  return query with recursive tree(id) as (
    select (selection->>'unit')::uuid union all
    select u.id from public.organization_units u join tree t on u.parent_id=t.id where u.is_active)
   select p.id,p.display_name,p.organization_unit_id,true from public.profiles p
   where p.is_active and (p.organization_unit_id in(select id from tree) or p.id=auth.uid());
 else
  return query select s.member,s.label,s.unit,s.managed from private.sales_scope_for((selection->>'subject')::uuid,true) s where s.member<>auth.uid()
   union all select p.id,p.display_name,p.organization_unit_id,manager from public.profiles p where p.id=auth.uid() and p.is_active;
 end if;
end $$;

