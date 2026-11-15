-- Additive conditional reads. Existing clients and all write policies stay unchanged.
create function private.sales_calendar_day_stamps(first_day date,last_day date,p_unit uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 with scope as materialized(select * from private.sales_scope()),
 allowed as materialized(select distinct unit from scope where auth.uid() is not null and private.sales_enabled()
  and exists(select 1 from scope where unit=p_unit)
  and (unit=p_unit or private.sales_view_selection() is not null)),
 access as (select coalesce((select string_agg(member::text||label||unit::text||managed::text,',' order by member) from scope),'')||
  coalesce((select string_agg(member::text||label,',' order by member) from private.sales_branch_members()),'') value),
 versions as (select v.day,string_agg(v.unit::text||':'||v.version::text,',' order by v.unit) value
  from private.sales_calendar_versions v join allowed a using(unit) where v.day between first_day and last_day group by v.day)
 select jsonb_object_agg(d.day::date::text,md5(coalesce(v.value,'')||access.value))
 from generate_series(first_day,last_day,interval '1 day') d(day)
 left join versions v on v.day=d.day::date cross join access
 where last_day-first_day between 0 and 62 and exists(select 1 from allowed)
$$;
revoke all on function private.sales_calendar_day_stamps(date,date,uuid) from public,anon;
grant execute on function private.sales_calendar_day_stamps(date,date,uuid) to authenticated;

create function public.sales_calendar_changes(first_day date,last_day date,p_member uuid default null,p_team boolean default false,p_known jsonb default null)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare me record; target_unit uuid; versions jsonb; lo date; hi date; result jsonb;
begin
 if auth.uid() is null or first_day is null or last_day is null or last_day-first_day not between 0 and 62 then
  raise exception 'Invalid calendar request' using errcode='22023';end if;
 select * into me from private.sales_scope() where member=auth.uid();
 if me.member is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 target_unit:=me.unit;
 if p_member is not null then
  if not me.managed then raise exception 'Calendar access denied' using errcode='42501';end if;
  select unit into target_unit from private.sales_scope() where member=p_member;
  if target_unit is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 end if;
 versions:=private.sales_calendar_day_stamps(first_day,last_day,target_unit);
 if versions is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 select min(key::date),max(key::date) into lo,hi from jsonb_each_text(versions)
 where value is distinct from p_known->>key;
 if lo is null then result:=jsonb_build_object('unchanged',true);
 else result:=public.sales_calendar_payload(lo,hi,p_member,p_team);end if;
 return result||jsonb_build_object('versions',versions,'replaceFirst',lo,'replaceLast',hi,
  'unit',target_unit,'stamp',private.sales_calendar_stamp(first_day,last_day,target_unit));
end $$;
revoke all on function public.sales_calendar_changes(date,date,uuid,boolean,jsonb) from public,anon;
grant execute on function public.sales_calendar_changes(date,date,uuid,boolean,jsonb) to authenticated;

-- Fetch the visible detail and feedback in one round trip under existing RLS.
-- Closed contract sections are fetched separately only when opened.
create function public.sales_calendar_detail(p_id uuid) returns jsonb
language plpgsql stable security invoker set search_path='' as $$
declare result jsonb;
begin
 select jsonb_build_object('row',to_jsonb(e),'reviews',coalesce((select jsonb_agg(to_jsonb(r) order by r.created_at desc)
 from public.sales_reviews r where r.event=e.id and r.deleted_at is null and r.message<>'일정 확인'),'[]'::jsonb))
 into result from public.sales_events e where e.id=p_id and e.deleted_at is null;
 if result is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 return result;
end $$;
revoke all on function public.sales_calendar_detail(uuid) from public,anon;
grant execute on function public.sales_calendar_detail(uuid) to authenticated;
