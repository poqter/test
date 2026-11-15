-- Apply before the matching application release. No account or business rows change.
-- Preserve the public stamp signature for already-open clients.
create or replace function private.sales_calendar_stamp(first_day date,last_day date,p_unit uuid)
returns text language sql stable security definer set search_path='' as $$
 with scope as materialized(select * from private.sales_scope()),
 allowed as (
  select distinct s.unit from scope s
  where auth.uid() is not null and private.sales_enabled()
   and exists(select 1 from scope where unit=p_unit)
   and (s.unit=p_unit or private.sales_view_selection() is not null)
 )
 select md5(
  coalesce((select string_agg(v.unit::text||':'||v.day::text||':'||v.version::text,',' order by v.unit,v.day)
   from private.sales_calendar_versions v join allowed a using(unit) where v.day between first_day and last_day),'')||
  coalesce((select string_agg(member::text||label||unit::text||managed::text,',' order by member) from scope),'')||
  coalesce((select string_agg(member::text||label,',' order by member) from private.sales_branch_members()),''))
 where last_day-first_day between 0 and 62 and exists(select 1 from allowed)
$$;

-- Branch summaries already expose schedule times. Add end times for the selected
-- companion only, without exposing titles, notes, place, support or other details.
create or replace function private.sales_companion_busy_times(first_day date,last_day date,p_member uuid)
returns table(id uuid,day date,start_time time,end_time time)
language plpgsql stable security definer set search_path='' as $$
begin
 if auth.uid() is null or not private.sales_enabled() or not exists(
  select 1 from private.sales_branch_members() b where b.member=p_member)
 then raise exception '동행자 조회 권한을 확인해 주세요' using errcode='42501';end if;
 if first_day is null or last_day is null or last_day-first_day not between 0 and 62
 then raise exception '조회 기간을 확인해 주세요' using errcode='22023';end if;
 return query select e.id,e.day,e.start_time,e.end_time
 from public.sales_events e join private.sales_branch_members() b on b.member=e.owner
 join public.profiles me on me.id=auth.uid()
 where (private.sales_view_selection() is not null or e.unit=me.organization_unit_id)
 and (e.owner=p_member or e.companion=p_member) and e.status='예정'
 and e.deleted_at is null and e.start_time is not null and e.day between first_day and last_day;
end $$;
create or replace function public.sales_companion_busy_times(first_day date,last_day date,p_member uuid)
returns table(id uuid,day date,start_time time,end_time time)
language sql stable security invoker set search_path='' as $$
 select * from private.sales_companion_busy_times(first_day,last_day,p_member)
$$;
revoke all on function private.sales_companion_busy_times(date,date,uuid),public.sales_companion_busy_times(date,date,uuid) from public,anon;
grant execute on function private.sales_companion_busy_times(date,date,uuid),public.sales_companion_busy_times(date,date,uuid) to authenticated;
revoke all on function private.sales_calendar_stamp(date,date,uuid) from public,anon;
grant execute on function private.sales_calendar_stamp(date,date,uuid) to authenticated;
