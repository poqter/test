-- Calendar summaries contain schedule titles and must check reporting scope.
-- Keep branch-wide common events visible without granting access to private details.
create or replace function private.sales_calendar_days_v2(first_day date,last_day date)
returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean,title text)
language sql stable security definer set search_path='' as $$
 with scope as materialized(select * from private.sales_scope()),
 viewer as (select s.unit,private.sales_view_selection() is not null as selected
  from scope s where s.member=auth.uid())
 select e.id,e.owner,e.day,e.start_time,e.kind,e.status,e.companion,e.common,e.time_pending,e.title
 from viewer v join public.sales_events e on (v.selected or v.unit=e.unit)
 where e.deleted_at is null and e.day between first_day and last_day
  and last_day-first_day between 0 and 62
  and (exists(select 1 from scope s where s.member=e.owner)
   or (e.common and (e.unit=v.unit or (v.selected and exists(select 1 from scope s where s.unit=e.unit)))))
$$;

create or replace function private.sales_calendar_days(first_day date,last_day date)
returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean)
language sql stable security definer set search_path='' as $$
 select d.id,d.owner,d.day,d.start_time,d.kind,d.status,d.companion,d.common,d.time_pending
 from private.sales_calendar_days_v2(first_day,last_day) d
$$;

-- Invalidate calendar payloads cached under the previous visibility rules.
CREATE OR REPLACE FUNCTION private.sales_calendar_stamp(first_day date, last_day date, p_unit uuid)
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
 with scope as materialized(select * from private.sales_scope()),
 allowed as (
  select distinct s.unit from scope s
  where auth.uid() is not null and private.sales_enabled()
   and exists(select 1 from scope where unit=p_unit)
   and (s.unit=p_unit or private.sales_view_selection() is not null)
 )
 select md5('calendar-reporting-scope-v1:'||
  coalesce((select string_agg(v.unit::text||':'||v.day::text||':'||v.version::text,',' order by v.unit,v.day)
   from private.sales_calendar_versions v join allowed a using(unit) where v.day between first_day and last_day),'')||
  coalesce((select string_agg(member::text||label||unit::text||managed::text,',' order by member) from scope),'')||
  coalesce((select string_agg(member::text||label,',' order by member) from private.sales_branch_members()),''))
 where last_day-first_day between 0 and 62 and exists(select 1 from allowed)
$function$;

CREATE OR REPLACE FUNCTION private.sales_calendar_day_stamps(first_day date, last_day date, p_unit uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
 with scope as materialized(select * from private.sales_scope()),
 allowed as materialized(select distinct unit from scope where auth.uid() is not null and private.sales_enabled()
  and exists(select 1 from scope where unit=p_unit)
  and (unit=p_unit or private.sales_view_selection() is not null)),
 access as (select coalesce((select string_agg(member::text||label||unit::text||managed::text,',' order by member) from scope),'')||
  coalesce((select string_agg(member::text||label,',' order by member) from private.sales_branch_members()),'') value),
 versions as (select v.day,string_agg(v.unit::text||':'||v.version::text,',' order by v.unit) value
  from private.sales_calendar_versions v join allowed a using(unit) where v.day between first_day and last_day group by v.day)
 select jsonb_object_agg(d.day::date::text,md5('calendar-reporting-scope-v1:'||coalesce(v.value,'')||access.value))
 from generate_series(first_day,last_day,interval '1 day') d(day)
 left join versions v on v.day=d.day::date cross join access
 where last_day-first_day between 0 and 62 and exists(select 1 from allowed)
$function$;
