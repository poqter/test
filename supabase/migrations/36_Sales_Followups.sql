create table public.sales_followups(
 id uuid primary key,owner uuid not null default auth.uid() references public.profiles,
 source uuid not null references public.sales_events, due date not null,
 title text not null check(length(trim(title)) between 1 and 200),scheduled uuid unique references public.sales_events);
alter table public.sales_followups enable row level security;
revoke all on public.sales_followups from public,anon,authenticated;
grant select,insert on public.sales_followups to authenticated;
grant update(scheduled) on public.sales_followups to authenticated;
create index sales_followup_due on public.sales_followups(owner,due) where scheduled is null;
create policy follow_read on public.sales_followups for select to authenticated using(owner in(select member from private.sales_scope()));
create policy follow_add on public.sales_followups for insert to authenticated with check(owner=auth.uid() and private.sales_enabled() and scheduled is null and exists(select from public.sales_events e where e.id=source and e.owner=auth.uid()));
create policy follow_edit on public.sales_followups for update to authenticated using(owner=auth.uid() and private.sales_enabled() and scheduled is null) with check(owner=auth.uid() and exists(select from public.sales_events e where e.id=scheduled and e.owner=auth.uid() and e.previous_event=source));
create function public.schedule_sales_followup(task uuid,schedule_day date,activity text) returns uuid language plpgsql security invoker set search_path='' as $$
declare f public.sales_followups;e public.sales_events; new_id uuid:=gen_random_uuid();
begin
 perform pg_advisory_xact_lock(hashtextextended(task::text,0));
 select * into strict f from public.sales_followups where id=task and owner=auth.uid();
 if f.scheduled is not null then return f.scheduled;end if;
 select * into strict e from public.sales_events where id=f.source;
 insert into public.sales_events(id,unit,day,kind,title,previous_event,time_pending)
 values(new_id,e.unit,schedule_day,activity,f.title,e.id,true);
 update public.sales_followups set scheduled=new_id where id=f.id;
 return new_id;
end $$;
revoke all on function public.schedule_sales_followup(uuid,date,text) from public,anon;
grant execute on function public.schedule_sales_followup(uuid,date,text) to authenticated;
