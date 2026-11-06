-- Additive migration: preserve events and all linked business records.
alter table public.sales_events add column deleted_at timestamptz, add column deletion_batch uuid, add column series_id uuid;
create index sales_event_unit_day on public.sales_events(unit,day);
create index sales_event_series on public.sales_events(owner,series_id,day) where series_id is not null;
create index sales_event_trash on public.sales_events(owner,deleted_at) where deleted_at is not null;
create table private.sales_calendar_versions(unit uuid not null,day date not null,version bigint not null default 1,primary key(unit,day));
revoke all on private.sales_calendar_versions from public,anon,authenticated;
create function private.sales_calendar_changed() returns trigger language plpgsql security definer set search_path='' as $$
declare r record;
begin
 for r in select distinct x.unit,x.day from (values(new.unit,new.day),(case when tg_op='UPDATE' then old.unit else new.unit end,case when tg_op='UPDATE' then old.day else new.day end)) x(unit,day) order by x.unit,x.day loop
 insert into private.sales_calendar_versions(unit,day) values(r.unit,r.day) on conflict(unit,day) do update set version=private.sales_calendar_versions.version+1;
 end loop;
 return new;
end $$;
create trigger sales_calendar_changed after insert or update on public.sales_events for each row execute function private.sales_calendar_changed();
create function private.sales_archive_guard() returns trigger language plpgsql set search_path='' as $$
begin
 if tg_op='INSERT' then
  if new.deleted_at is not null or new.deletion_batch is not null then raise exception '삭제 상태로 등록할 수 없습니다'; end if;
 else
  if new.series_id is distinct from old.series_id then raise exception '반복 묶음은 변경할 수 없습니다'; end if;
  if old.deleted_at is not null then
   if (to_jsonb(new)-array['deleted_at','deletion_batch','revision']) is distinct from (to_jsonb(old)-array['deleted_at','deletion_batch','revision']) then raise exception '삭제된 일정은 먼저 복구해 주세요'; end if;
   if new.deleted_at is null and old.deleted_at<now()-interval '30 days' then raise exception '복구 기간이 지났습니다'; end if;
   if new.deleted_at is not null then new.deleted_at=old.deleted_at;new.deletion_batch=old.deletion_batch;end if;
  elsif new.deleted_at is not null then new.deleted_at=now(); end if;
  if new.deleted_at is null then new.deletion_batch=null; end if;
 end if;
 return new;
end $$;
create trigger sales_archive_guard before insert or update on public.sales_events for each row execute function private.sales_archive_guard();
-- RLS still decides visibility and ownership. This RPC never uses service credentials.
create function public.sales_archive_event(p_id uuid,p_revision integer,p_future boolean default false,p_restore boolean default false) returns integer language plpgsql security invoker set search_path='' as $$
declare e public.sales_events;r record;n integer:=0;batch uuid:=gen_random_uuid();
begin
 perform pg_advisory_xact_lock(hashtextextended('sales.archive.'||auth.uid()::text,0));
 select * into e from public.sales_events where id=p_id and owner=auth.uid() for update;
 if not found then raise exception '본인의 일정만 변경할 수 있습니다';end if;
 if e.revision<>p_revision then
  if (p_restore and e.deleted_at is null) or (not p_restore and e.deleted_at is not null) then return 0;end if;
  raise exception '다른 기기에서 변경되었습니다. 최신 내용을 확인해 주세요';
 end if;
 if p_restore then
  if e.deleted_at is null then return 0;end if;
  if e.deleted_at<now()-interval '30 days' then raise exception '복구 기간이 지났습니다';end if;
  update public.sales_events set deleted_at=null,deletion_batch=null where id=p_id and owner=auth.uid();return 1;
 end if;
 if e.deleted_at is not null then return 0;end if;
 for r in select id from public.sales_events where owner=auth.uid() and deleted_at is null and (id=p_id or (p_future and e.series_id is not null and series_id=e.series_id and day>=e.day)) order by day,id for update loop
  update public.sales_events set deleted_at=now(),deletion_batch=batch where id=r.id;
  n:=n+1;
 end loop;
 return n;
end $$;
create function private.sales_calendar_stamp(first_day date,last_day date,p_unit uuid) returns text language sql stable security definer set search_path='' as $$
 with scope as materialized(select * from private.sales_scope()), allowed as(select p_unit as unit where private.sales_enabled() and exists(select 1 from scope where unit=p_unit))
 select md5(coalesce((select string_agg(v.day::text||':'||v.version::text,',' order by v.day) from private.sales_calendar_versions v join allowed a using(unit) where v.day between first_day and last_day),'')||coalesce((select string_agg(member::text||label||managed::text,',' order by member) from scope),'')||coalesce((select string_agg(member::text||label,',' order by member) from private.sales_branch_members()),'')) where last_day-first_day between 0 and 62 and exists(select 1 from allowed)
$$;
create function public.sales_calendar_stamp(first_day date,last_day date,p_unit uuid) returns text language sql stable security invoker set search_path='' as $$select private.sales_calendar_stamp(first_day,last_day,p_unit)$$;
revoke all on function private.sales_calendar_changed(),private.sales_archive_guard(),private.sales_calendar_stamp(date,date,uuid),public.sales_calendar_stamp(date,date,uuid),public.sales_archive_event(uuid,integer,boolean,boolean) from public,anon;
grant execute on function private.sales_calendar_stamp(date,date,uuid),public.sales_calendar_stamp(date,date,uuid),public.sales_archive_event(uuid,integer,boolean,boolean) to authenticated;
create or replace function private.sales_calendar_days(first_day date,last_day date) returns table(id uuid,owner uuid,day date,start_time time,kind text,status text,companion uuid,common boolean,time_pending boolean) language sql stable security definer set search_path='' as $$
 select e.id,e.owner,e.day,e.start_time,e.kind,e.status,e.companion,e.common,e.time_pending from public.sales_events e join private.sales_branch_members() b on b.member=e.owner join public.profiles me on me.id=auth.uid() and me.organization_unit_id=e.unit where e.deleted_at is null and e.day between first_day and last_day and last_day-first_day between 0 and 62
$$;
create or replace function public.sales_edit_event(p_id uuid,p_revision integer,p_data jsonb,p_follow date,p_follow_id uuid)
returns boolean language plpgsql security invoker set search_path='' as $$
declare updated public.sales_events;
begin
 update public.sales_events set
 companion=case when p_data ? 'companion' then (p_data->>'companion')::uuid else companion end,
 time_pending=case when p_data ? 'time_pending' then (p_data->>'time_pending')::boolean else time_pending end,
 day=(p_data->>'day')::date,start_time=(p_data->>'start_time')::time,end_time=(p_data->>'end_time')::time,
 title=p_data->>'title',kind=p_data->>'kind',place=p_data->>'place',note=p_data->>'note',
 help=p_data->>'help',common=(p_data->>'common')::boolean,status=p_data->>'status',result=p_data->>'result'
 where id=p_id and revision=p_revision and deleted_at is null returning * into updated;
 if not found then return false; end if;
 if p_follow is not null then
   if p_follow_id is null or p_follow<updated.day then
     raise exception '후속 일정 날짜를 확인해 주세요';
   end if;
   insert into public.sales_events(id,owner,unit,day,start_time,end_time,kind,title,place,note,common,companion,time_pending,previous_event,contact_method)
   values(p_follow_id,updated.owner,updated.unit,p_follow,updated.start_time,updated.end_time,updated.kind,
          updated.title,updated.place,updated.note,updated.common,updated.companion,updated.time_pending,updated.id,updated.contact_method);
 end if;
 return true;
end $$;
create or replace function public.sales_qa_snapshot(subject uuid,first_day date,last_day date) returns jsonb
language sql stable security invoker set search_path='' as $$
 with scope as (select * from private.sales_scope_for(subject,true) where managed and private.sales_admin())
 select jsonb_build_object('members',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from scope s),
 'events',(select coalesce(jsonb_agg(to_jsonb(e) order by day,start_time nulls first),'[]') from public.sales_events e join scope s on s.member=e.owner where e.deleted_at is null and e.day between first_day and last_day),
 'reports',(select coalesce(jsonb_agg(to_jsonb(r)),'[]') from public.sales_reports r join scope s on s.member=r.owner where r.submitted and r.day between first_day and last_day))
$$;
