-- Search the existing calendar visibility boundary; places only come from caller RLS.
create function public.sales_calendar_search(p_query text,first_day date,last_day date,p_member uuid default null,p_team boolean default false,p_offset integer default 0)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare me record; needle text:=lower(btrim(p_query)); result jsonb;
begin
 if auth.uid() is null or not private.sales_enabled() then raise exception 'Calendar access denied' using errcode='42501';end if;
 if needle is null or length(needle) not between 1 and 100 or first_day is null or last_day is null
 or last_day-first_day not between 0 and 365 or p_offset is null or p_offset not between 0 and 10000 then
 raise exception '검색어와 기간을 확인해 주세요. 검색 기간은 최대 1년입니다.' using errcode='22023';end if;
 select * into me from private.sales_scope() where member=auth.uid();
 if me.member is null or (p_member is not null and (not me.managed or not exists(select 1 from private.sales_scope() where member=p_member))) then
 raise exception 'Calendar access denied' using errcode='42501';end if;
 with summaries as (
  select s.* from generate_series(0,(last_day-first_day)/63) n
  cross join lateral private.sales_calendar_days_v2(first_day+n*63,least(last_day,first_day+n*63+62)) s
 ), matches as (
  select s.id,s.owner,s.day,s.start_time,s.kind,s.status,s.time_pending,s.title,
  e.id is not null readable,e.place,b.label owner_label
  from summaries s left join public.sales_events e on e.id=s.id and e.deleted_at is null
  left join private.sales_branch_members() b on b.member=s.owner
  where (case when p_member is not null then s.owner=p_member else p_team or s.owner=auth.uid() or s.companion=auth.uid() or s.common end)
  and (strpos(lower(coalesce(s.title,'')),needle)>0 or strpos(lower(coalesce(e.place,'')),needle)>0)
  order by s.day,s.start_time nulls last,s.id offset p_offset limit 21
 ), numbered as (select *,row_number() over(order by day,start_time nulls last,id) n from matches)
 select jsonb_build_object('rows',coalesce(jsonb_agg(to_jsonb(numbered)-'n' order by n) filter(where n<=20),'[]'::jsonb),
 'hasMore',count(*)>20) into result from numbered;
 return result;
end $$;
revoke all on function public.sales_calendar_search(text,date,date,uuid,boolean,integer) from public,anon;
grant execute on function public.sales_calendar_search(text,date,date,uuid,boolean,integer) to authenticated;
