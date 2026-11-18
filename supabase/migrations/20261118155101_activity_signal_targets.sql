create or replace function private.sales_activity_changed() returns trigger language plpgsql security definer set search_path='' as $$
declare item jsonb; who uuid; on_day date; topic_name text; target record;
begin
 if tg_table_name='profiles' and tg_op='UPDATE' and (to_jsonb(old)-array['updated_at','last_seen_at','last_login_at'])=(to_jsonb(new)-array['updated_at','last_seen_at','last_login_at']) then return null;end if;
 -- A title or count edit has two row images but only one affected owner and day.
 for item in
  select distinct case when tg_table_name in ('sales_events','sales_reports')
                       then jsonb_build_object('owner',v->'owner','day',v->'day')
                       else v end as signal_source
  from (values (case when tg_op <> 'INSERT' then to_jsonb(old) end),
               (case when tg_op <> 'DELETE' then to_jsonb(new) end)) images(v)
  where v is not null order by signal_source
 loop
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
