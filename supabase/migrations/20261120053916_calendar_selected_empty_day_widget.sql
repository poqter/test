-- Keep ownership/access checks; allow the selected calendar date instead of only today.
alter policy empty_add on public.sales_empty_days with check (
 owner=auth.uid() and private.sales_enabled() and day between date '1900-01-01' and date '2100-12-31'
);

-- Small widget payload, under the existing caller RLS and calendar access checks.
create function public.sales_widget_month(first_day date,last_day date,p_team boolean default false)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare result jsonb; empty_days jsonb;
begin
 if first_day is null or last_day is null or last_day<first_day or last_day-first_day>62 then raise exception '날짜 범위를 확인해 주세요.';end if;
 result:=public.sales_calendar_compact(first_day,last_day,null,p_team,null);
 select coalesce(jsonb_agg(day),'[]'::jsonb) into empty_days from public.sales_empty_days
 where owner=auth.uid() and day between first_day and last_day;
 return result||jsonb_build_object('empty_days',empty_days);
end $$;
revoke all on function public.sales_widget_month(date,date,boolean) from public,anon;
grant execute on function public.sales_widget_month(date,date,boolean) to authenticated;

-- No caller-supplied owner; conflict/active-event protection remains atomic in triggers.
create function public.sales_empty_day_set(p_day date,p_confirmed boolean default true)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare confirmed boolean;
begin
 if p_day is null or p_day not between date '1900-01-01' and date '2100-12-31' or p_confirmed is null then raise exception '등록할 날짜를 확인해 주세요.';end if;
 if not coalesce(private.sales_enabled(),false) then raise exception '일정 등록 권한이 없습니다.' using errcode='42501';end if;
 if p_confirmed then
  insert into public.sales_empty_days(day) values(p_day) on conflict do nothing;
 else
  delete from public.sales_empty_days where owner=auth.uid() and day=p_day;
 end if;
 select exists(select 1 from public.sales_empty_days where owner=auth.uid() and day=p_day) into confirmed;
 if confirmed<>p_confirmed then raise exception '저장 결과를 확인하지 못했습니다.';end if;
 return jsonb_build_object('day',p_day,'confirmed',confirmed);
end $$;
revoke all on function public.sales_empty_day_set(date,boolean) from public,anon;
grant execute on function public.sales_empty_day_set(date,boolean) to authenticated;
