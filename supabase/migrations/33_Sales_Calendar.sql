alter table public.sales_events add column companion uuid references public.profiles(id), add column time_pending boolean not null default false;
create index sales_companion_day on public.sales_events(companion,day) where companion is not null;
create table public.sales_empty_days(owner uuid default auth.uid() references public.profiles, day date not null,primary key(owner,day));
alter table public.sales_empty_days enable row level security;
revoke all on public.sales_empty_days from public,anon,authenticated;
grant select,insert,delete on public.sales_empty_days to authenticated;
create policy empty_read on public.sales_empty_days for select to authenticated using(owner in(select member from private.sales_scope()));
create policy empty_add on public.sales_empty_days for insert to authenticated with check(owner=auth.uid() and private.sales_enabled() and day=(now() at time zone 'Asia/Seoul')::date);
create policy empty_remove on public.sales_empty_days for delete to authenticated using(owner=auth.uid() and private.sales_enabled());
create function private.sales_companion_check() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.companion is not null and (new.companion=new.owner or not exists(select from public.profiles p where p.id=new.companion and p.is_active and p.organization_unit_id=new.unit)) then raise exception 'invalid companion'; end if;
 return new;
end $$;
create trigger sales_companion_check before insert or update of companion,unit on public.sales_events for each row execute function private.sales_companion_check();
revoke all on function private.sales_companion_check() from public,anon,authenticated;
create function private.sales_branch_members() returns table(member uuid,label text) language sql stable security definer set search_path='' as $$
 select p.id,p.display_name from public.profiles p join public.profiles me on me.organization_unit_id=p.organization_unit_id where me.id=auth.uid() and p.is_active and private.sales_enabled()
$$;
create function public.sales_branch_members() returns table(member uuid,label text) language sql stable security invoker set search_path='' as $$select * from private.sales_branch_members()$$;
create function private.sales_calendar_days(first_day date,last_day date) returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean) language sql stable security definer set search_path='' as $$
 select e.id,e.owner,e.day,e.start_time,e.kind,e.status,e.companion,e.common,e.time_pending from public.sales_events e join private.sales_branch_members() b on b.member=e.owner join public.profiles me on me.id=auth.uid() and me.organization_unit_id=e.unit where e.day between first_day and last_day and last_day-first_day between 0 and 62
$$;
create function public.sales_calendar_days(first_day date,last_day date) returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean) language sql stable security invoker set search_path='' as $$select * from private.sales_calendar_days(first_day,last_day)$$;
alter policy event_read on public.sales_events using(owner in(select member from private.sales_scope()));
revoke all on function private.sales_branch_members(),public.sales_branch_members(),private.sales_calendar_days(date,date),public.sales_calendar_days(date,date) from public,anon;
grant execute on function private.sales_branch_members(),public.sales_branch_members(),private.sales_calendar_days(date,date),public.sales_calendar_days(date,date) to authenticated;
create or replace function public.sales_edit_event(p_id uuid,p_revision integer,p_data jsonb,p_follow date,p_follow_id uuid)
returns boolean language plpgsql security invoker set search_path='' as $$
declare updated public.sales_events;
begin
 update public.sales_events set companion=case when p_data ? 'companion' then (p_data->>'companion')::uuid else companion end,time_pending=case when p_data ? 'time_pending' then (p_data->>'time_pending')::boolean else time_pending end,day=(p_data->>'day')::date,start_time=(p_data->>'start_time')::time,
 end_time=(p_data->>'end_time')::time,title=p_data->>'title',kind=p_data->>'kind',place=p_data->>'place',
 note=p_data->>'note',help=p_data->>'help',common=(p_data->>'common')::boolean,status=p_data->>'status',result=p_data->>'result'
 where id=p_id and revision=p_revision returning * into updated;
 if not found then return false; end if;
 if p_follow is not null then
 insert into public.sales_events(id,owner,unit,day,start_time,end_time,kind,title,place,note,common)
 values(p_follow_id,updated.owner,updated.unit,p_follow,updated.start_time,updated.end_time,updated.kind,updated.title,updated.place,updated.note,updated.common);
 end if;
 return true;
end $$;
