create table public.sales_notices(
 id uuid primary key default gen_random_uuid(), recipient uuid not null references public.profiles,
 event uuid not null references public.sales_events, message text not null,
 created_at timestamptz not null default now(), seen boolean not null default false);
create index sales_notice_inbox on public.sales_notices(recipient,seen,created_at);
alter table public.sales_notices enable row level security;
revoke all on public.sales_notices from public,anon,authenticated;
grant select,update(seen) on public.sales_notices to authenticated;
create policy sales_notices_read on public.sales_notices for select to authenticated using
 (recipient=auth.uid() and exists(select 1 from public.sales_events e where e.id=event));
create policy sales_notices_seen on public.sales_notices for update to authenticated using
 (recipient=auth.uid() and exists(select 1 from public.sales_events e where e.id=event)) with check(recipient=auth.uid());
create function private.sales_notify() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if tg_table_name='sales_reviews' then
  if new.event is not null then
   insert into public.sales_notices(recipient,event,message)
   select e.owner,e.id,case when new.message='동행 수락' then '동행 요청을 수락했습니다.' else '일정에 새 의견이 있습니다.' end
   from public.sales_events e where e.id=new.event and e.owner<>new.reviewer;
  end if;
 else
  if (new.day,new.start_time,new.end_time,new.status,new.place) is distinct from (old.day,old.start_time,old.end_time,old.status,old.place) then
   insert into public.sales_notices(recipient,event,message)
   select distinct r.reviewer,new.id,'동행할 일정이 변경되었습니다.' from public.sales_reviews r
   where r.event=new.id and r.message='동행 수락' and r.reviewer<>new.owner;
  end if;
 end if;
 return new;
end $$;
revoke all on function private.sales_notify() from public,anon,authenticated;
create trigger sales_notice_reply after insert on public.sales_reviews for each row execute function private.sales_notify();
create trigger sales_notice_change after update on public.sales_events for each row execute function private.sales_notify();
