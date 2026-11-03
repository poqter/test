alter table public.sales_events add column previous_event uuid references public.sales_events(id),add column created_at timestamptz,add column contact_method text check(contact_method in ('전화','메시지')),add column case_id uuid;
alter table public.sales_events alter column created_at set default now();
create index sales_events_previous on public.sales_events(previous_event);
create index sales_events_case on public.sales_events(case_id);
create function private.sales_case_insert() returns trigger language plpgsql security definer set search_path='' as $$
declare parent public.sales_events;
begin
 new.created_at=now();
 if new.previous_event is null then new.case_id=new.id;
 else
 select * into strict parent from public.sales_events where id=new.previous_event and owner=new.owner;
 if parent.day>new.day then raise exception '후속 일정 날짜를 확인해 주세요'; end if;
 new.case_id=coalesce(parent.case_id,parent.id);
 end if;
 return new;
end $$;
create trigger sales_case_insert before insert on public.sales_events for each row execute function private.sales_case_insert();
create function private.sales_case_update() returns trigger language plpgsql set search_path='' as $$
begin
 if new.previous_event is distinct from old.previous_event or new.case_id is distinct from old.case_id or new.created_at is distinct from old.created_at then raise exception '상담 연결을 변경할 수 없습니다';end if;
 return new;
end $$;
create trigger sales_case_update before update on public.sales_events for each row execute function private.sales_case_update();
revoke all on function private.sales_case_insert(),private.sales_case_update() from public,anon,authenticated;
