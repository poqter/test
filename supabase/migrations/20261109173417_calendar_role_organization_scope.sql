-- Session-only view selection. No account or organization rows are modified.
create function private.sales_view_catalog() returns jsonb
language sql stable security definer set search_path='' as $$
 select jsonb_build_object(
 'positions',(select jsonb_agg(jsonb_build_object('code',code,'display_name',display_name) order by rank_order desc) from public.positions where is_active),
 'units',(select jsonb_agg(jsonb_build_object('id',id,'name',name,'parent_id',parent_id,'unit_type',unit_type) order by sort_order,name) from public.organization_units where is_active),
 'people',(select coalesce(jsonb_agg(jsonb_build_object('id',id,'display_name',display_name,'position_code',position_code,'organization_unit_id',organization_unit_id)),'[]'::jsonb) from public.profiles where is_active))
 where private.sales_admin()
$$;
create function public.sales_view_catalog() returns jsonb language sql stable security invoker set search_path='' as $$select private.sales_view_catalog()$$;
revoke all on function private.sales_view_catalog(),public.sales_view_catalog() from public,anon;
grant execute on function private.sales_view_catalog(),public.sales_view_catalog() to authenticated;

create function private.sales_view_selection() returns jsonb
language plpgsql stable security definer set search_path='' as $$
declare raw text; selection jsonb;
begin
 if not private.sales_admin() then return null; end if;
 raw := coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-hwarang-view-scope','daily');
 if left(raw,1)<>'{' then return null; end if;
 selection:=raw::jsonb;
 if not exists(select 1 from public.positions where code=selection->>'position' and is_active)
 or not exists(select 1 from public.organization_units where id=(selection->>'unit')::uuid and is_active)
 then raise exception 'Invalid viewing scope' using errcode='22023'; end if;
 if selection->>'position' not in ('chief_representative','division_head','branch_manager') and not exists(
 select 1 from public.profiles where id=(selection->>'subject')::uuid and is_active
 and position_code=selection->>'position' and organization_unit_id=(selection->>'unit')::uuid)
 then raise exception 'Invalid viewing subject' using errcode='22023'; end if;
 return selection;
end $$;
revoke all on function private.sales_view_selection() from public,anon;
grant execute on function private.sales_view_selection() to authenticated;

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
 manager:=selection->>'position' in ('chief_representative','division_head','branch_manager','team_leader');
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

create or replace function private.sales_branch_members() returns table(member uuid,label text)
language sql stable security definer set search_path='' as $$
 select s.member,s.label from private.sales_scope() s where private.sales_view_selection() is not null
 union all
 select p.id,p.display_name from public.profiles p join public.profiles me on me.organization_unit_id=p.organization_unit_id
 where me.id=auth.uid() and p.is_active and private.sales_enabled() and private.sales_view_selection() is null
$$;

create or replace function private.sales_calendar_days_v2(first_day date,last_day date)
returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean,title text)
language sql stable security definer set search_path='' as $$
 select e.id,e.owner,e.day,e.start_time,e.kind,e.status,e.companion,e.common,e.time_pending,e.title
 from public.sales_events e join private.sales_branch_members() b on b.member=e.owner
 join public.profiles me on me.id=auth.uid()
 where auth.uid() is not null and (private.sales_view_selection() is not null or me.organization_unit_id=e.unit)
 and e.deleted_at is null and e.day between first_day and last_day and last_day-first_day between 0 and 62
$$;

create or replace function public.sales_calendar_payload(first_day date,last_day date,p_member uuid default null,p_team boolean default false)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare me record; target_unit uuid; result jsonb;
begin
 if auth.uid() is null or first_day is null or last_day is null or last_day-first_day not between 0 and 62 then raise exception 'Invalid calendar request' using errcode='22023';end if;
 select * into me from private.sales_scope() where member=auth.uid();
 if me.member is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 target_unit:=me.unit;
 if p_member is not null then
  if not me.managed then raise exception 'Calendar access denied' using errcode='42501';end if;
  select unit into target_unit from private.sales_scope() where member=p_member;
  if target_unit is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 end if;
 select jsonb_build_object(
 'rows',coalesce((select jsonb_agg(jsonb_build_object('id',e.id,'owner',e.owner,'day',e.day,'start_time',e.start_time,'kind',e.kind,'status',e.status,'companion',e.companion,'common',e.common,'time_pending',e.time_pending,'title',e.title,'revision',e.revision,'place',e.place,'help',coalesce(e.help,'')<>''))
 from public.sales_events e where e.deleted_at is null and e.day between first_day and last_day and
 ((p_member is not null and e.owner=p_member) or (p_member is null and (e.unit=target_unit or (private.sales_view_selection() is not null and e.owner in(select member from private.sales_scope()))) and (p_team or e.owner=auth.uid() or e.companion=auth.uid() or e.common)))),'[]'::jsonb),
 'summary',case when p_member is null then coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_calendar_days_v2(first_day,last_day) s where p_team or s.owner=auth.uid() or s.companion=auth.uid() or s.common),'[]'::jsonb) else '[]'::jsonb end,
 'branch',coalesce((select jsonb_agg(to_jsonb(b)) from private.sales_branch_members() b),'[]'::jsonb),
 'unit',target_unit,'stamp',private.sales_calendar_stamp(first_day,last_day,target_unit)) into result;
 return result;
end $$;
revoke all on function public.sales_calendar_payload(date,date,uuid,boolean) from public,anon;
grant execute on function public.sales_calendar_payload(date,date,uuid,boolean) to authenticated;

