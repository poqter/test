-- Delete only the explicitly selected owned event(s); no historical bulk purge.
alter table public.sales_followups alter column source drop not null;
alter table public.sales_contracts drop constraint sales_contracts_event_fkey, add constraint sales_contracts_event_fkey foreign key (event) references public.sales_events(id) on delete set null;
alter table public.sales_followups drop constraint sales_followups_source_fkey, add constraint sales_followups_source_fkey foreign key (source) references public.sales_events(id) on delete set null;
alter table public.sales_followups drop constraint sales_followups_scheduled_fkey, add constraint sales_followups_scheduled_fkey foreign key (scheduled) references public.sales_events(id) on delete set null;
alter table public.sales_events drop constraint sales_events_previous_event_fkey, add constraint sales_events_previous_event_fkey foreign key (previous_event) references public.sales_events(id) on delete set null;
alter table public.sales_notices drop constraint sales_notices_event_fkey, add constraint sales_notices_event_fkey foreign key (event) references public.sales_events(id) on delete cascade;
alter table public.sales_reviews drop constraint sales_reviews_event_fkey, add constraint sales_reviews_event_fkey foreign key (event) references public.sales_events(id) on delete cascade;

create or replace function private.sales_case_update() returns trigger language plpgsql set search_path='' as $$
begin
 if (new.previous_event is distinct from old.previous_event and not (new.previous_event is null and not exists(select 1 from public.sales_events where id=old.previous_event)))
 or new.case_id is distinct from old.case_id or new.created_at is distinct from old.created_at then raise exception '상담 연결을 변경할 수 없습니다';end if;
 return new;
end $$;
create or replace function private.sales_archive_guard() returns trigger language plpgsql set search_path='' as $$
begin
 if tg_op='INSERT' then
  if new.deleted_at is not null or new.deletion_batch is not null then raise exception '삭제 상태로 등록할 수 없습니다'; end if;
 else
  if new.series_id is distinct from old.series_id then raise exception '반복 묶음은 변경할 수 없습니다'; end if;
  if old.deleted_at is not null and new.previous_event is null and old.previous_event is not null and not exists(select 1 from public.sales_events where id=old.previous_event) then return new; end if;
  if old.deleted_at is not null then
   if (to_jsonb(new)-array['deleted_at','deletion_batch','revision']) is distinct from (to_jsonb(old)-array['deleted_at','deletion_batch','revision']) then raise exception '삭제된 일정은 먼저 복구해 주세요'; end if;
   if new.deleted_at is null and old.deleted_at<now()-interval '30 days' then raise exception '복구 기간이 지났습니다'; end if;
   if new.deleted_at is not null then new.deleted_at=old.deleted_at;new.deletion_batch=old.deletion_batch;end if;
  elsif new.deleted_at is not null then new.deleted_at=now(); end if;
  if new.deleted_at is null then new.deletion_batch=null; end if;
 end if;
 return new;
end $$;

create function private.sales_delete_event(p_id uuid,p_revision integer,p_future boolean default false) returns integer
language plpgsql security definer set search_path='' as $$
declare e public.sales_events; n integer;
begin
 if auth.uid() is null or not private.sales_enabled() then raise exception '일정 삭제 권한이 없습니다' using errcode='42501';end if;
 perform pg_advisory_xact_lock(hashtextextended('sales.delete.'||auth.uid()::text,0));
 select * into e from public.sales_events where id=p_id and owner=auth.uid() for update;
 if not found then raise exception '본인의 일정만 삭제할 수 있습니다' using errcode='42501';end if;
 if e.revision<>p_revision then raise exception '다른 기기에서 변경되었습니다. 최신 내용을 확인해 주세요';end if;
 delete from public.sales_events where owner=auth.uid() and (id=p_id or (p_future and e.series_id is not null and series_id=e.series_id and day>=e.day));
 get diagnostics n=row_count;
 return n;
end $$;
create function public.sales_delete_event(p_id uuid,p_revision integer,p_future boolean default false) returns integer
language sql security invoker set search_path='' as $$select private.sales_delete_event(p_id,p_revision,p_future)$$;
revoke all on function private.sales_delete_event(uuid,integer,boolean),public.sales_delete_event(uuid,integer,boolean) from public,anon;
grant execute on function private.sales_delete_event(uuid,integer,boolean),public.sales_delete_event(uuid,integer,boolean) to authenticated;
-- Old open clients also delete immediately; restoration is no longer offered.
create or replace function public.sales_archive_event(p_id uuid,p_revision integer,p_future boolean default false,p_restore boolean default false) returns integer
language plpgsql security invoker set search_path='' as $$
begin
 if p_restore then raise exception '일정 복구 기능은 종료되었습니다';end if;
 return public.sales_delete_event(p_id,p_revision,p_future);
end $$;
create function private.sales_calendar_deleted() returns trigger language plpgsql security definer set search_path='' as $$
begin
 insert into private.sales_calendar_versions(unit,day) values(old.unit,old.day)
 on conflict(unit,day) do update set version=private.sales_calendar_versions.version+1;
 return old;
end $$;
revoke all on function private.sales_calendar_deleted() from public,anon,authenticated;
create trigger sales_calendar_deleted after delete on public.sales_events for each row execute function private.sales_calendar_deleted();
-- A detached follow-up can still be scheduled under its owner's real unit.
create or replace function public.schedule_sales_followup(task uuid,schedule_day date,activity text) returns uuid
language plpgsql security invoker set search_path='' as $$
declare f public.sales_followups;e public.sales_events; new_id uuid:=gen_random_uuid(); target_unit uuid;
begin
 perform pg_advisory_xact_lock(hashtextextended(task::text,0));
 select * into strict f from public.sales_followups where id=task and owner=auth.uid();
 if f.scheduled is not null then return f.scheduled;end if;
 if f.source is not null then
  select * into strict e from public.sales_events where id=f.source;
  target_unit:=e.unit;
 else
  select unit into target_unit from private.sales_scope() where member=auth.uid();
 end if;
 insert into public.sales_events(id,unit,day,kind,title,previous_event,time_pending)
 values(new_id,target_unit,schedule_day,activity,f.title,e.id,true);
 update public.sales_followups set scheduled=new_id where id=f.id;
 return new_id;
end $$;
alter policy follow_edit on public.sales_followups to authenticated
 using(owner=auth.uid() and private.sales_enabled() and scheduled is null)
 with check(owner=auth.uid() and exists(select 1 from public.sales_events e where e.id=scheduled and e.owner=auth.uid() and e.previous_event is not distinct from source));
