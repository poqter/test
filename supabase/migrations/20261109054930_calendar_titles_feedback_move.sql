-- Add title to the existing branch summary without widening detail RLS.
create function private.sales_calendar_days_v2(first_day date,last_day date)
returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean,title text)
language sql stable security definer set search_path='' as $$
 select e.id,e.owner,e.day,e.start_time,e.kind,e.status,e.companion,e.common,e.time_pending,e.title
 from public.sales_events e join private.sales_branch_members() b on b.member=e.owner
 join public.profiles me on me.id=auth.uid() and me.organization_unit_id=e.unit
 where auth.uid() is not null and e.deleted_at is null and e.day between first_day and last_day and last_day-first_day between 0 and 62
$$;
create function public.sales_calendar_days_v2(first_day date,last_day date)
returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean,title text)
language sql stable security invoker set search_path='' as $$select * from private.sales_calendar_days_v2(first_day,last_day)$$;
revoke all on function private.sales_calendar_days_v2(date,date),public.sales_calendar_days_v2(date,date) from public,anon;
grant execute on function private.sales_calendar_days_v2(date,date),public.sales_calendar_days_v2(date,date) to authenticated;

-- Existing feedback and confirmation rows are retained. Deletion is recoverable.
alter table public.sales_reviews add column updated_at timestamptz,add column deleted_at timestamptz,add column edit_version integer not null default 1;
grant update(message,deleted_at) on public.sales_reviews to authenticated;
create policy review_author_update on public.sales_reviews for update to authenticated
 using(reviewer=auth.uid() and event is not null and deleted_at is null and exists(select 1 from public.sales_events e where e.id=event and e.owner in(select member from private.sales_scope())))
 with check(reviewer=auth.uid() and event is not null and exists(select 1 from public.sales_events e where e.id=event and e.owner in(select member from private.sales_scope())));
create function private.sales_review_version() returns trigger language plpgsql security invoker set search_path='' as $$
begin
 if length(btrim(new.message)) not between 1 and 4000 then raise exception 'Invalid feedback';end if;
 new.updated_at=now();new.edit_version=old.edit_version+1;return new;
end $$;
revoke all on function private.sales_review_version() from public,anon,authenticated;
create trigger sales_review_version before update on public.sales_reviews for each row execute function private.sales_review_version();

create or replace function public.sales_calendar_payload(first_day date,last_day date,p_member uuid default null,p_team boolean default false)
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
 'rows',coalesce((select jsonb_agg(jsonb_build_object('id',e.id,'owner',e.owner,'day',e.day,'start_time',e.start_time,'kind',e.kind,'status',e.status,'companion',e.companion,'common',e.common,'time_pending',e.time_pending,'title',e.title,'revision',e.revision,'place',e.place,'help',coalesce(e.help,'')<>''))
 from public.sales_events e where e.deleted_at is null and e.day between first_day and last_day and
 ((p_member is not null and e.owner=p_member) or (p_member is null and e.unit=target_unit and (p_team or e.owner=auth.uid() or e.companion=auth.uid() or e.common)))),'[]'::jsonb),
 'summary',case when p_member is null then coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_calendar_days_v2(first_day,last_day) s where p_team or s.owner=auth.uid() or s.companion=auth.uid() or s.common),'[]'::jsonb) else '[]'::jsonb end,
 'branch',coalesce((select jsonb_agg(to_jsonb(b)) from private.sales_branch_members() b),'[]'::jsonb),
 'unit',target_unit,'stamp',private.sales_calendar_stamp(first_day,last_day,target_unit)) into result;
 return result;
end $$;
revoke all on function public.sales_calendar_payload(date,date,uuid,boolean) from public,anon;
grant execute on function public.sales_calendar_payload(date,date,uuid,boolean) to authenticated;

