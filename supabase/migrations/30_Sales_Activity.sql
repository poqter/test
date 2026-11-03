insert into public.hwarang_permissions(permission_code,app_code,group_label,display_name,description,sort_order,default_granted)
values ('workspace.sales_activity','workspace','영업활동','영업활동 관리','캘린더와 일일·주간 활동 기록',7,true);
-- Private helpers bind every check to the caller's live workspace session.
create function private.sales_enabled() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.profiles p join public.hwarang_app_access a on a.user_id=p.id
 join auth.sessions s on s.user_id=p.id and s.id=(auth.jwt()->>'session_id')::uuid
 where p.id=auth.uid() and p.is_active and a.app_code='workspace' and a.is_enabled and exists(select 1 from public.get_hwarang_effective_permissions(p.id) ep where ep.permission_code='workspace.sales_activity'))
$$;
create function private.sales_scope() returns table(member uuid,label text,unit uuid,managed boolean)
language sql stable security definer set search_path='' as $$
 with recursive me as (select * from public.profiles where id=auth.uid() and private.sales_enabled()),
 tree(id) as (select organization_unit_id from me union select u.id from public.organization_units u join tree on u.parent_id=tree.id where u.is_active),
 members as (select p.*, (me.role='super_admin' or (me.position_code in ('branch_manager','division_head','chief_representative')
 and p.organization_unit_id in (select id from tree))) as managed from me cross join public.profiles p where p.is_active)
 select id,display_name,organization_unit_id,managed from members where id=auth.uid() or managed
$$;
create function public.sales_members() returns table(member uuid,label text,unit uuid,managed boolean)
language sql stable security invoker set search_path='' as $$ select * from private.sales_scope() $$;
create table public.sales_events(
 id uuid primary key, owner uuid not null default auth.uid() references public.profiles, unit uuid not null references public.organization_units,
 day date not null, start_time time, end_time time, kind text not null, title text not null check(length(title) between 1 and 200),
 place text not null default '', note text not null default '', common boolean not null default false,
 status text not null default '예정' check(status in ('예정','완료','연기','취소')), result text not null default '',
 help text not null default '', revision integer not null default 1, check(end_time is null or start_time < end_time));
create index sales_event_day on public.sales_events(day,owner);
create table public.sales_reports(
 id uuid primary key, owner uuid not null default auth.uid() references public.profiles, period text not null check(period in ('일일','주간')),
 day date not null, submitted boolean not null default false, data jsonb not null, revision integer not null default 1,
 changed_at timestamptz not null default now(), unique(owner,period,day));
create table public.sales_reviews(
 id uuid primary key, report uuid references public.sales_reports, event uuid references public.sales_events,
 reviewer uuid not null default auth.uid() references public.profiles, revision integer not null,
 message text not null, created_at timestamptz not null default now(),check(num_nonnulls(report,event)=1));
create table public.sales_report_history(report uuid references public.sales_reports, revision integer, data jsonb not null, changed_at timestamptz, primary key(report,revision));
create function private.sales_version() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.id<>old.id or new.owner<>old.owner then raise exception 'identity change'; end if;
 if tg_table_name='sales_reports' then
  if new.day<>old.day or new.period<>old.period or (old.submitted and not new.submitted) then raise exception 'invalid report change'; end if;
  if old.submitted then insert into public.sales_report_history values(old.id,old.revision,old.data,old.changed_at); end if;
  new.changed_at=now();
 end if;
 new.revision=old.revision+1;return new;
end $$;
create trigger sales_report_version before update on public.sales_reports for each row execute function private.sales_version();
create trigger sales_event_version before update on public.sales_events for each row execute function private.sales_version();
alter table public.sales_events enable row level security;
alter table public.sales_reports enable row level security;
alter table public.sales_reviews enable row level security;
alter table public.sales_report_history enable row level security;
revoke all on public.sales_events,public.sales_reports,public.sales_reviews,public.sales_report_history from public,anon,authenticated;
grant select,insert,update on public.sales_events,public.sales_reports to authenticated;
grant select,insert on public.sales_reviews to authenticated;
grant select on public.sales_report_history to authenticated;
create policy event_read on public.sales_events for select to authenticated using(owner in(select member from private.sales_scope()) or (common and unit in(select unit from private.sales_scope())));
create policy event_insert on public.sales_events for insert to authenticated with check(owner=auth.uid() and exists(select 1 from private.sales_scope() s where s.member=auth.uid() and s.unit=sales_events.unit and (not common or s.managed)));
create policy event_edit on public.sales_events for update to authenticated using(owner=auth.uid() and private.sales_enabled()) with check(owner=auth.uid() and exists(select 1 from private.sales_scope() s where s.member=auth.uid() and s.unit=sales_events.unit and (not common or s.managed)));
create policy report_read on public.sales_reports for select to authenticated using(private.sales_enabled() and (owner=auth.uid() or (submitted and owner in(select member from private.sales_scope() where managed))));
create policy report_insert on public.sales_reports for insert to authenticated with check(owner=auth.uid() and private.sales_enabled());
create policy report_edit on public.sales_reports for update to authenticated using(owner=auth.uid() and private.sales_enabled()) with check(owner=auth.uid() and private.sales_enabled());
create policy history_read on public.sales_report_history for select to authenticated using(exists(select 1 from public.sales_reports r where r.id=report));
create policy review_read on public.sales_reviews for select to authenticated using(exists(select 1 from public.sales_reports r where r.id=report) or exists(select 1 from public.sales_events e where e.id=event and e.owner in(select member from private.sales_scope())));
create policy review_insert on public.sales_reviews for insert to authenticated with check(reviewer=auth.uid() and (exists(select 1 from public.sales_reports r where r.id=report and r.submitted and r.revision=sales_reviews.revision and r.owner in(select member from private.sales_scope() where managed)) or exists(select 1 from public.sales_events e where e.id=event and e.revision=sales_reviews.revision and e.owner in(select member from private.sales_scope() where managed))));
revoke all on function private.sales_enabled(),private.sales_scope(),public.sales_members(),private.sales_version() from public,anon;
grant execute on function private.sales_enabled(),private.sales_scope(),public.sales_members() to authenticated;
create table public.sales_devices(
 digest text primary key, owner uuid not null references public.profiles, secret text not null,
 issued_at timestamptz not null default now(), expires_at timestamptz not null default(now()+interval '30 days'));
create index sales_devices_owner on public.sales_devices(owner);
alter table public.sales_devices enable row level security;
revoke all on public.sales_devices from public,anon,authenticated;
grant select,insert,update,delete on public.sales_devices to service_role;
create function private.sales_revoke_device() returns trigger language plpgsql security definer set search_path='' as $$
begin
 delete from public.sales_devices where owner=new.user_id;
 return new;
end $$;
create trigger sales_credentials_changed after insert or update on public.hwarang_account_security for each row execute function private.sales_revoke_device();
revoke all on function private.sales_revoke_device() from public;
-- Mutate the original and its follow-up in one transaction under caller RLS.
create function public.sales_edit_event(p_id uuid,p_revision integer,p_data jsonb,p_follow date,p_follow_id uuid)
returns boolean language plpgsql security invoker set search_path='' as $$
declare updated public.sales_events;
begin
 update public.sales_events set day=(p_data->>'day')::date,start_time=(p_data->>'start_time')::time,
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
revoke all on function public.sales_edit_event(uuid,integer,jsonb,date,uuid) from public,anon;
grant execute on function public.sales_edit_event(uuid,integer,jsonb,date,uuid) to authenticated;
create function private.sales_disabled() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if tg_table_name='profiles' then
  if not new.is_active then delete from public.sales_devices where owner=new.id; end if;
 elsif new.app_code='workspace' and not new.is_enabled then
  delete from public.sales_devices where owner=new.user_id;
 end if;
 return new;
end $$;
create trigger sales_disabled_user after update of is_active on public.profiles for each row execute function private.sales_disabled();
create trigger sales_disabled_app after update of is_enabled on public.hwarang_app_access for each row execute function private.sales_disabled();
revoke all on function private.sales_disabled() from public;
