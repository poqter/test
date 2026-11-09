-- Single, validated support recipient; delivery is atomic with source persistence.
alter table public.sales_events add column help_recipient uuid references public.profiles;
alter table public.sales_notices alter column event drop not null;
alter table public.sales_notices add column report uuid references public.sales_reports on delete cascade;
alter table public.sales_notices add column support_key text unique;
create index sales_notice_report on public.sales_notices(report);
create index sales_event_help_recipient on public.sales_events(help_recipient);
alter table public.sales_notices add constraint notice_source_present check(event is not null or report is not null);

create function private.sales_support_candidates(subject uuid)
returns table(member uuid,label text,role_code text) language sql stable security definer set search_path='' as $$
 select p.id,coalesce(p.display_name,p.login_id),p.position_code
 from public.profiles me join public.profiles p on p.organization_unit_id=me.organization_unit_id
 where me.id=subject and p.is_active and p.id<>subject and (
 p.position_code='branch_manager' or
 p.position_code='team_leader' and exists(select 1 from public.sales_team_assignments a where a.member=subject and a.leader=p.id) or
 p.position_code='deputy_branch_manager' and exists(select 1 from public.sales_deputy_assignments a where a.member=subject and a.leader=p.id))
$$;
revoke all on function private.sales_support_candidates(uuid) from public,anon,authenticated;
create function private.sales_support_recipients() returns table(member uuid,label text,role_code text)
language sql stable security definer set search_path='' as $$
 select * from private.sales_support_candidates(auth.uid()) where auth.uid() is not null and private.sales_enabled()
$$;
revoke all on function private.sales_support_recipients() from public,anon;
grant execute on function private.sales_support_recipients() to authenticated;
create function public.sales_support_recipients() returns table(member uuid,label text,role_code text)
language sql stable security invoker set search_path='' as $$ select * from private.sales_support_recipients() $$;
revoke all on function public.sales_support_recipients() from public,anon;
grant execute on function public.sales_support_recipients() to authenticated;

create function private.sales_support_notify() returns trigger language plpgsql security definer set search_path='' as $$
declare target uuid; content text; previous_content text; previous_target uuid; sender text; source_label text; fingerprint text;
begin
 if tg_table_name='sales_events' then
  content:=btrim(coalesce(new.help,''));target:=new.help_recipient;
  if tg_op='UPDATE' then previous_content:=btrim(coalesce(old.help,''));previous_target:=old.help_recipient;end if;
  if new.deleted_at is not null or new.status in ('취소','연기') then return new;end if;
  source_label:=new.day::text||' · '||new.title;
 else
  if not new.submitted then return new;end if;
  content:=btrim(coalesce(new.data->>'help',''));target:=nullif(new.data->>'help_recipient','')::uuid;
  if tg_op='UPDATE' and old.submitted then previous_content:=btrim(coalesce(old.data->>'help',''));previous_target:=nullif(old.data->>'help_recipient','')::uuid;end if;
  source_label:=new.day::text||case when new.period='주간' then ' ~ '||(new.day+6)::text else '' end||' · '||new.period||' 활동 기록';
 end if;
 if content='' then return new;end if;
 -- Preserve untouched historical requests that predate recipient selection.
 if target is null and content=previous_content and previous_target is null then return new;end if;
 if target is null or not exists(select 1 from private.sales_support_candidates(new.owner) c where c.member=target)
 then raise exception '연결된 관리자 중 지원 요청 대상을 선택해 주세요' using errcode='23514';end if;
 if content=previous_content and target=previous_target then return new;end if;
 select coalesce(display_name,login_id) into sender from public.profiles where id=new.owner;
 fingerprint:=tg_table_name||':'||new.id::text||':'||target::text||':'||md5(content);
 insert into public.sales_notices(recipient,event,report,message,support_key)
 values(target,case when tg_table_name='sales_events' then new.id end,case when tg_table_name='sales_reports' then new.id end,
 sender||'님이 지원을 요청했습니다.'||E'\n'||source_label||E'\n'||content,fingerprint)
 on conflict(support_key) do nothing;
 return new;
end $$;
revoke all on function private.sales_support_notify() from public,anon,authenticated;
create trigger sales_support_event after insert or update on public.sales_events for each row execute function private.sales_support_notify();
create trigger sales_support_report after insert or update on public.sales_reports for each row execute function private.sales_support_notify();

-- Keep the existing optimistic revision check and all scheduling behavior.
do $$ declare definition text;begin
 select pg_get_functiondef('public.sales_edit_event(uuid,integer,jsonb,date,uuid)'::regprocedure) into definition;
 if position('help=p_data->>''help''' in definition)=0 then raise exception 'Unexpected event function version';end if;
 definition:=replace(definition,'help=p_data->>''help''','help_recipient=case when p_data ? ''help_recipient'' then nullif(p_data->>''help_recipient'','''')::uuid else help_recipient end,help=p_data->>''help''');
 execute definition;
end $$;

drop policy sales_notices_read on public.sales_notices;
create policy sales_notices_read on public.sales_notices for select to authenticated using
 (recipient=auth.uid() and private.sales_enabled() and
 (exists(select 1 from public.sales_events e where e.id=event) or exists(select 1 from public.sales_reports r where r.id=report and r.submitted)));
drop policy sales_notices_seen on public.sales_notices;
create policy sales_notices_seen on public.sales_notices for update to authenticated using
 (recipient=auth.uid() and private.sales_enabled() and
 (exists(select 1 from public.sales_events e where e.id=event) or exists(select 1 from public.sales_reports r where r.id=report and r.submitted))) with check(recipient=auth.uid());
