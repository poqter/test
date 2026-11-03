create table public.sales_team_assignments (
 member uuid primary key references public.profiles(id),
 leader uuid not null references public.profiles(id), check(member <> leader)
);
alter table public.sales_team_assignments enable row level security;
revoke all on public.sales_team_assignments from public,anon,authenticated;
grant select, insert, update, delete on public.sales_team_assignments to authenticated;
create function private.sales_admin() returns boolean language sql stable security definer set search_path='' as $$
 select private.sales_enabled() and exists(select 1 from public.profiles where id=auth.uid() and role='super_admin')
$$;
create policy assignments_admin on public.sales_team_assignments to authenticated using(private.sales_admin()) with check(private.sales_admin());
create function private.sales_scope_for(subject uuid,preview boolean) returns table(member uuid,label text,unit uuid,managed boolean)
language sql stable security definer set search_path='' as $$
 with recursive me as (select * from public.profiles where id=subject and is_active and private.sales_enabled() and (subject=auth.uid() or private.sales_admin())),
 tree(id) as (select organization_unit_id from me union select u.id from public.organization_units u join tree on u.parent_id=tree.id where u.is_active),
 members as (select p.*, ((me.role='super_admin' and not preview) or (me.position_code in ('branch_manager','division_head','chief_representative')
 and p.organization_unit_id in (select id from tree)) or (me.position_code='team_leader' and p.organization_unit_id=me.organization_unit_id and
 (p.id=subject or exists(select 1 from public.sales_team_assignments a where a.leader=subject and a.member=p.id)))) as managed
 from me cross join public.profiles p where p.is_active)
 select id,display_name,organization_unit_id,managed from members where id=subject or managed
$$;
create or replace function private.sales_scope() returns table(member uuid,label text,unit uuid,managed boolean)
language sql stable security definer set search_path='' as $$ select * from private.sales_scope_for(auth.uid(),false) $$;
create function public.sales_qa_snapshot(subject uuid,first_day date,last_day date) returns jsonb
language sql stable security invoker set search_path='' as $$
 with scope as (select * from private.sales_scope_for(subject,true) where managed and private.sales_admin())
 select jsonb_build_object('members',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from scope s),
 'events',(select coalesce(jsonb_agg(to_jsonb(e) order by day,start_time nulls first),'[]') from public.sales_events e join scope s on s.member=e.owner where e.day between first_day and last_day),
 'reports',(select coalesce(jsonb_agg(to_jsonb(r)),'[]') from public.sales_reports r join scope s on s.member=r.owner where r.submitted and r.day between first_day and last_day))
$$;
revoke all on function private.sales_admin(),private.sales_scope_for(uuid,boolean),public.sales_qa_snapshot(uuid,date,date) from public,anon;
grant execute on function private.sales_admin(),private.sales_scope_for(uuid,boolean),public.sales_qa_snapshot(uuid,date,date) to authenticated;
