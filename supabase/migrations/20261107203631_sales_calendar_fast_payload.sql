-- Additive read endpoints. All schedule detail reads retain caller RLS.
create function public.sales_calendar_context() returns jsonb language sql stable security invoker set search_path='' as $$
 select jsonb_build_object('members',coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_scope() s),'[]'::jsonb),
 'branch',coalesce((select jsonb_agg(to_jsonb(b)) from private.sales_branch_members() b),'[]'::jsonb))
$$;
revoke all on function public.sales_calendar_context() from public,anon;
grant execute on function public.sales_calendar_context() to authenticated;

create function public.sales_calendar_payload(first_day date,last_day date,p_member uuid default null,p_team boolean default false)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare me record; target_unit uuid; result jsonb;
begin
 if auth.uid() is null or first_day is null or last_day is null or last_day-first_day not between 0 and 62 then raise exception 'Invalid calendar request' using errcode='22023';end if;
 select * into me from private.sales_scope() where member=auth.uid();
 if me.member is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 target_unit:=me.unit;
 if p_member is not null then
  if not me.managed then raise exception 'Calendar access denied' using errcode='42501';end if;
  select unit into target_unit from private.sales_scope() where member=p_member;
  if target_unit is null then raise exception 'Calendar access denied' using errcode='42501';end if;
 end if;
 select jsonb_build_object(
 'rows',coalesce((select jsonb_agg(jsonb_build_object('id',e.id,'owner',e.owner,'day',e.day,'start_time',e.start_time,'kind',e.kind,'status',e.status,'companion',e.companion,'common',e.common,'time_pending',e.time_pending,'title',e.title,'help',coalesce(e.help,'')<>''))
 from public.sales_events e where e.deleted_at is null and e.day between first_day and last_day and
 ((p_member is not null and e.owner=p_member) or (p_member is null and e.unit=target_unit and (p_team or e.owner=auth.uid() or e.companion=auth.uid() or e.common)))),'[]'::jsonb),
 'summary',case when p_member is null then coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_calendar_days(first_day,last_day) s where p_team or s.owner=auth.uid() or s.companion=auth.uid() or s.common),'[]'::jsonb) else '[]'::jsonb end,
 'branch',coalesce((select jsonb_agg(to_jsonb(b)) from private.sales_branch_members() b),'[]'::jsonb),
 'unit',target_unit,'stamp',private.sales_calendar_stamp(first_day,last_day,target_unit)) into result;
 return result;
end $$;
revoke all on function public.sales_calendar_payload(date,date,uuid,boolean) from public,anon;
grant execute on function public.sales_calendar_payload(date,date,uuid,boolean) to authenticated;

-- Notification rows contain only unit/version; no customer or schedule content.
create table public.sales_calendar_signals(unit uuid primary key,version bigint not null default 1);
alter table public.sales_calendar_signals enable row level security;
revoke all on public.sales_calendar_signals from public,anon,authenticated;
grant select on public.sales_calendar_signals to authenticated;
create policy sales_calendar_signals_read on public.sales_calendar_signals for select to authenticated
 using(auth.uid() is not null and private.sales_enabled() and unit in(select s.unit from private.sales_scope() s));
create function private.sales_calendar_signal() returns trigger language plpgsql security definer set search_path='' as $$
begin
 -- Trigger-only function: the original sales_events write has already passed RLS.
 if tg_op<>'INSERT' then
  insert into public.sales_calendar_signals(unit) values(old.unit) on conflict(unit) do update set version=sales_calendar_signals.version+1;
 end if;
 if tg_op='INSERT' or (tg_op='UPDATE' and new.unit is distinct from old.unit) then
  insert into public.sales_calendar_signals(unit) values(new.unit) on conflict(unit) do update set version=sales_calendar_signals.version+1;
 end if;
 return null;
end $$;
revoke all on function private.sales_calendar_signal() from public,anon,authenticated;
create trigger sales_calendar_signal after insert or update or delete on public.sales_events for each row execute function private.sales_calendar_signal();
do $$begin
 if exists(select 1 from pg_publication where pubname='supabase_realtime') then
  alter publication supabase_realtime add table public.sales_calendar_signals;
 end if;
end$$;
