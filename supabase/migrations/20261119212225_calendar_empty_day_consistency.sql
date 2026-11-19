-- Explicit empty-day confirmation is removed atomically by a new active personal event.
-- No historical rows are rewritten. Common/cancelled/postponed/archived events do not clear it.
create function private.sales_event_clear_empty_day() returns trigger
language plpgsql security definer set search_path='' as $$
declare member_id uuid;
begin
 if new.common or new.deleted_at is not null or new.status in ('취소','연기') then return new;end if;
 if not exists(select 1 from public.profiles p where p.id=new.owner and p.is_active and p.organization_unit_id=new.unit) then return new;end if;
 for member_id in select p.id from public.profiles p
 where p.id in (new.owner,new.companion) and p.is_active and p.organization_unit_id=new.unit order by p.id loop
  perform pg_advisory_xact_lock(hashtextextended(member_id::text||':'||new.day::text,20261120));
  delete from public.sales_empty_days where owner=member_id and day=new.day;
 end loop;
 return new;
end $$;
create trigger sales_empty_day_clear before insert or update of owner,companion,day,common,status,deleted_at,unit
on public.sales_events for each row execute function private.sales_event_clear_empty_day();

-- Serialize explicit confirmation with event writes so concurrent requests cannot leave both.
create function private.sales_empty_day_guard() returns trigger
language plpgsql security definer set search_path='' as $$
begin
 perform pg_advisory_xact_lock(hashtextextended(new.owner::text||':'||new.day::text,20261120));
 if exists(select 1 from public.sales_events e
 join public.profiles author on author.id=e.owner and author.is_active and author.organization_unit_id=e.unit
 join public.profiles member on member.id=new.owner and member.is_active and member.organization_unit_id=e.unit
 where new.owner in (e.owner,e.companion) and e.day=new.day
 and not e.common and e.deleted_at is null and e.status not in ('취소','연기')) then
  raise exception '오늘 개인 일정 또는 휴무가 등록되어 있습니다. 기존 일정을 확인해 주세요.';
 end if;
 return new;
end $$;
create trigger sales_empty_day_guard before insert or update on public.sales_empty_days
for each row execute function private.sales_empty_day_guard();
revoke all on function private.sales_event_clear_empty_day(),private.sales_empty_day_guard() from public,anon,authenticated,service_role;
