-- Additive: existing submissions, review history, authentication and RLS stay intact.
create table public.sales_activity_signals (
 owner uuid not null references public.profiles(id) on delete cascade,
 topic text not null, day date not null, version bigint not null default 1,
 primary key(owner,topic,day)
);
alter table public.sales_activity_signals enable row level security;
revoke all on public.sales_activity_signals from public,anon,authenticated;
grant select on public.sales_activity_signals to authenticated;
create policy activity_signal_read on public.sales_activity_signals for select to authenticated
using(owner=auth.uid() or (private.sales_enabled() and exists(select 1 from private.sales_scope() s where s.member=owner)));

create function private.sales_activity_changed() returns trigger language plpgsql security definer set search_path='' as $$
declare item jsonb; who uuid; on_day date; topic_name text; target record;
begin
 if tg_table_name='profiles' and tg_op='UPDATE' and (to_jsonb(old)-array['updated_at','last_seen_at','last_login_at'])=(to_jsonb(new)-array['updated_at','last_seen_at','last_login_at']) then return null;end if;
 for item in select distinct v from (values(case when tg_op<>'INSERT' then to_jsonb(old) end),(case when tg_op<>'DELETE' then to_jsonb(new) end)) x(v) where v is not null loop
  who:=null; on_day:=null; topic_name:=tg_table_name;
  if tg_table_name in ('sales_events','sales_reports','sales_contracts','sales_empty_days') then
   who:=(item->>'owner')::uuid;on_day:=(item->>'day')::date;
  elsif tg_table_name in ('sales_reviews','sales_report_checks') then
   if item->>'report' is not null then select r.owner,r.day into who,on_day from public.sales_reports r where r.id=(item->>'report')::uuid;
   elsif item->>'event' is not null then select e.owner,e.day into who,on_day from public.sales_events e where e.id=(item->>'event')::uuid;end if;
  elsif tg_table_name='sales_notices' then
   who:=(item->>'recipient')::uuid;on_day:='1900-01-01';
  else
   -- Membership changes invalidate every active account's scope, including revoked users.
   for target in select id from public.profiles order by id loop
    insert into public.sales_activity_signals(owner,topic,day) values(target.id,'scope','1900-01-01')
    on conflict(owner,topic,day) do update set version=sales_activity_signals.version+1;
   end loop;
  end if;
  if who is not null and on_day is not null and exists(select 1 from public.profiles where id=who) then
   insert into public.sales_activity_signals(owner,topic,day) values(who,topic_name,on_day)
   on conflict(owner,topic,day) do update set version=sales_activity_signals.version+1;
  end if;
 end loop;
 return null;
end $$;
revoke all on function private.sales_activity_changed() from public,anon,authenticated;
do $$declare t text;begin
 foreach t in array array['sales_events','sales_reports','sales_contracts','sales_empty_days','sales_reviews','sales_report_checks','profiles','sales_team_assignments','sales_deputy_assignments','organization_units'] loop
  execute format('create trigger activity_sync_changed after insert or update or delete on public.%I for each row execute function private.sales_activity_changed()',t);
 end loop;
 if exists(select 1 from pg_publication where pubname='supabase_realtime') then
  alter publication supabase_realtime add table public.sales_activity_signals;
 end if;
end $$;

create function public.sales_activity_stamp(p_first date,p_last date,p_owner uuid default null) returns text
language plpgsql stable security invoker set search_path='' as $$
declare result text;
begin
 if auth.uid() is null or not private.sales_enabled() then raise exception '조회 권한을 확인해 주세요' using errcode='42501';end if;
 if p_first is null or p_last is null or p_last<p_first or p_last-p_first>366 then raise exception '조회 기간을 확인해 주세요';end if;
 select md5(coalesce(string_agg(s.owner::text||s.topic||s.day::text||s.version::text,',' order by s.owner,s.topic,s.day),'')) into result
 from public.sales_activity_signals s where (s.day='1900-01-01' or s.day between p_first and p_last) and (p_owner is null or s.owner=p_owner or s.topic='scope');
 return result;
end $$;

create function public.sales_activity_bundle(p_first date,p_last date,p_owner uuid default null) returns jsonb
language plpgsql stable security invoker set search_path='' as $$
begin
 if auth.uid() is null or not private.sales_enabled() then raise exception '조회 권한을 확인해 주세요' using errcode='42501';end if;
 if p_first is null or p_last is null or p_last<p_first or p_last-p_first>366 then raise exception '조회 기간을 확인해 주세요';end if;
 return jsonb_build_object(
  'stamp',public.sales_activity_stamp(p_first,p_last,p_owner),
  'reports',coalesce((select jsonb_agg(to_jsonb(r) order by r.day,r.id) from public.sales_reports r where r.day between p_first and p_last and (p_owner is null or r.owner=p_owner)),'[]'::jsonb),
  'events',coalesce((select jsonb_agg(to_jsonb(e) order by e.day,e.id) from public.sales_events e where e.day between p_first and p_last and e.deleted_at is null and (p_owner is null or e.owner=p_owner)),'[]'::jsonb),
  'contracts',coalesce((select jsonb_agg(to_jsonb(c) order by c.day,c.id) from public.sales_contracts c where c.day between p_first and p_last and (p_owner is null or c.owner=p_owner)),'[]'::jsonb));
end $$;

-- All checks and feedback commit together, bound to the exact daily versions displayed.
create function public.sales_check_daily_period(p_owner uuid,p_first date,p_last date,p_versions jsonb,p_message text,p_request uuid) returns boolean
language plpgsql security invoker set search_path='' as $$
declare actual jsonb;r record;last_report uuid;last_revision integer;
begin
 if auth.uid() is null or not private.sales_enabled() or not exists(select 1 from private.sales_scope() s where s.member=p_owner and s.managed) then raise exception '검토 권한을 확인해 주세요' using errcode='42501';end if;
 if p_first is null or p_last is null or p_last<p_first or p_last-p_first>366 or p_request is null then raise exception '검토 기간을 확인해 주세요';end if;
 perform pg_advisory_xact_lock(hashtextextended('daily.review.'||auth.uid()::text||p_owner::text,0));
 for r in select * from public.sales_reports where owner=p_owner and period='일일' and submitted and day between p_first and p_last order by id for share loop
  actual:=coalesce(actual,'{}'::jsonb)||jsonb_build_object(r.id::text,r.revision);
 end loop;
 if actual is null or actual is distinct from p_versions then raise exception '일일 기록이 변경되었습니다. 최신 내용을 확인한 뒤 다시 처리해 주세요';end if;
 for r in select * from public.sales_reports where id::text in(select jsonb_object_keys(actual)) order by day,id loop
  perform public.sales_check_report(r.id,r.revision);last_report:=r.id;last_revision:=r.revision;
 end loop;
 if length(trim(coalesce(p_message,'')))>0 then
  insert into public.sales_reviews(id,report,revision,message) values(p_request,last_report,last_revision,'['||p_first::text||' ~ '||p_last::text||'] '||trim(p_message)) on conflict(id) do nothing;
 end if;
 return true;
end $$;
revoke all on function public.sales_activity_stamp(date,date,uuid),public.sales_activity_bundle(date,date,uuid),public.sales_check_daily_period(uuid,date,date,jsonb,text,uuid) from public,anon;
grant execute on function public.sales_activity_stamp(date,date,uuid),public.sales_activity_bundle(date,date,uuid),public.sales_check_daily_period(uuid,date,date,jsonb,text,uuid) to authenticated;
