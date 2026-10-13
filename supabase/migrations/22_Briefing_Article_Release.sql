-- Additive release migration. Apply AFTER 21. No account/data reset, no policy activation.
begin;
create table if not exists public.hwarang_briefing_share_components (
 token text not null references public.hwarang_briefing_public_shares(token) on delete cascade,
 revision_id uuid not null references public.hwarang_briefing_revisions(id),
 primary key(token,revision_id)
);
alter table public.hwarang_briefing_share_components enable row level security;
revoke all on public.hwarang_briefing_share_components from public,anon,authenticated;
grant select,insert,update,delete on public.hwarang_briefing_share_components to service_role;
create or replace function public.hwarang_publish_briefing(p_briefing uuid,p_revision uuid,p_actor uuid default null)
returns boolean language plpgsql security definer set search_path='' as $$
declare r public.hwarang_briefing_revisions; s public.hwarang_briefing_snapshots; allowed boolean;
begin
 if p_actor is not null and not exists(select 1 from public.profiles u where u.id=p_actor and u.is_active
 and (u.role='super_admin' or exists(select 1 from public.get_hwarang_effective_permissions(p_actor) where permission_code='workspace.briefing_manage'))) then
 raise exception 'Briefing manager required'; end if;
 perform 1 from public.hwarang_briefings where id=p_briefing for update;
 select * into r from public.hwarang_briefing_revisions where id=p_revision and briefing_id=p_briefing for update;
 if not found or r.validation_status<>'ok' or r.coverage_status<>'healthy' or r.publication_status='hidden' then
  raise exception 'Briefing validation incomplete';
 end if;
 if p_actor is null and not exists(select 1 from public.hwarang_briefing_operating_policy where policy_key='WORKSPACE' and automatic_publication_enabled) then
  raise exception 'Automatic publication approval required';
 end if;
 if p_actor is null and (now() at time zone 'Asia/Seoul') <
   (select briefing_date + case when profile_code='MARKET' then time '07:30' else time '08:00' end
    from public.hwarang_briefings where id=p_briefing) then
  raise exception 'Scheduled publication time not reached';
 end if;
 select * into s from public.hwarang_briefing_snapshots where revision_id=r.id;
 if not found or coalesce(s.qa_payload->>'internal_body_ready','')<>'true' then raise exception 'Internal body validation incomplete'; end if;
 if coalesce(jsonb_typeof(s.content_payload->'issues'),'null')<>'array' then raise exception 'Issues missing'; end if;
 if jsonb_array_length(s.content_payload->'issues')<1 then raise exception 'Insufficient issues'; end if;
 allowed=coalesce(s.qa_payload->>'public_body_ready','')='true'
   and exists(select 1 from public.hwarang_briefing_operating_policy where policy_key='WORKSPACE' and external_sharing_approved);
 update public.hwarang_briefing_revisions set publication_status='published',published_at=now(),
  external_qa_passed=coalesce(s.qa_payload->>'public_body_ready','')='true',external_share_allowed=allowed,approved_by=p_actor where id=r.id;
 update public.hwarang_briefings set current_published_revision_id=r.id where id=p_briefing;
 insert into public.hwarang_briefing_audit_log(actor_type,actor_user_id,action,briefing_id,revision_id,details)
 values(case when p_actor is null then 'system' else 'user' end,p_actor,'BRIEFING_PUBLISHED',p_briefing,r.id,jsonb_build_object('external_allowed',allowed));
 return true;
end $$;


-- Atomically register only still-current, same-date, QA-passed components.
create or replace function public.hwarang_register_combined_share(p_token text,p_sender uuid,p_revisions uuid[],p_packet jsonb)
returns boolean language plpgsql security definer set search_path='' as $$
declare v_id uuid; v_day date; v_date date; v_code text; v_codes text[] := '{}';
begin
 if p_token !~ '^[A-Za-z0-9_-]{32,64}$' or coalesce(cardinality(p_revisions),0) not between 1 and 3
 or coalesce(p_packet->>'schema','')<>'hwarang-share-v3' then raise exception 'Invalid share packet'; end if;
 if not exists(select 1 from public.profiles where id=p_sender and is_active)
 or not exists(select 1 from public.hwarang_briefing_operating_policy where policy_key='WORKSPACE' and external_sharing_approved)
 then raise exception 'Sharing not approved'; end if;
 foreach v_id in array p_revisions loop
  select b.briefing_date,b.profile_code into v_date,v_code
  from public.hwarang_briefing_revisions r
  join public.hwarang_briefings b on b.id=r.briefing_id and b.current_published_revision_id=r.id
  join public.hwarang_briefing_snapshots s on s.revision_id=r.id
  where r.id=v_id and r.publication_status='published' and r.validation_status='ok' and r.coverage_status='healthy'
   and r.external_share_allowed and r.external_qa_passed
   and s.qa_payload->>'public_body_ready'='true' and s.qa_payload->>'internal_body_ready'='true'
  for share of b,r;
  if not found or v_code=any(v_codes) or (v_day is not null and v_day<>v_date) then
   raise exception 'Component no longer shareable'; end if;
  v_day=v_date;v_codes=array_append(v_codes,v_code);
 end loop;
 if coalesce(p_packet->>'briefing_date','')<>v_day::text then raise exception 'Edition date mismatch'; end if;
 insert into public.hwarang_briefing_public_shares(token,revision_id,sender_user_id,public_packet)
 values(p_token,p_revisions[1],p_sender,p_packet);
 insert into public.hwarang_briefing_share_components(token,revision_id) select p_token,unnest(p_revisions);
 return true;
end $$;

-- Update dependency and anchor pointers in one transaction after a correction.
create or replace function public.hwarang_refresh_briefing_share(p_token text,p_old uuid,p_new uuid,p_packet jsonb)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 perform 1 from public.hwarang_briefing_public_shares where token=p_token for update;
 if not exists(select 1 from public.hwarang_briefing_revisions n
  join public.hwarang_briefing_revisions o on o.id=p_old and o.briefing_id=n.briefing_id
  join public.hwarang_briefings b on b.id=n.briefing_id and b.current_published_revision_id=n.id
  where n.id=p_new and n.publication_status='published' and n.external_qa_passed and n.external_share_allowed)
 then raise exception 'Correction not shareable'; end if;
 if not exists(select 1 from public.hwarang_briefing_public_shares where token=p_token and revision_id=p_old)
 and not exists(select 1 from public.hwarang_briefing_share_components where token=p_token and revision_id=p_old)
 then raise exception 'Share dependency changed'; end if;
 update public.hwarang_briefing_share_components set revision_id=p_new where token=p_token and revision_id=p_old;
 update public.hwarang_briefing_public_shares set public_packet=p_packet,
  revision_id=case when revision_id=p_old then p_new else revision_id end where token=p_token;
 return true;
end $$;
revoke all on function public.hwarang_refresh_briefing_share(text,uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.hwarang_refresh_briefing_share(text,uuid,uuid,jsonb) to service_role;

-- Every HTML/PDF/preview read checks ALL components, including non-anchor sections.
create or replace function public.hwarang_read_public_briefing(p_token text)
returns jsonb language sql stable security definer set search_path='' as $$
 select ps.public_packet from public.hwarang_briefing_public_shares ps
 join public.hwarang_briefing_operating_policy op on op.policy_key='WORKSPACE' and op.external_sharing_approved
 join public.profiles u on u.id=ps.sender_user_id and u.is_active
 where ps.token=p_token and ps.revoked_at is null and ps.expires_at>now()
 and p_token ~ '^[A-Za-z0-9_-]{32,64}$' and ps.public_packet->>'schema'='hwarang-share-v3'
 and not exists (
  select 1 from (
   select ps.revision_id as revision_id
   union select c.revision_id from public.hwarang_briefing_share_components c where c.token=ps.token
  ) x
  left join public.hwarang_briefing_revisions r on r.id=x.revision_id
  left join public.hwarang_briefings b on b.id=r.briefing_id
  left join public.hwarang_briefing_snapshots s on s.revision_id=r.id
  where r.id is null or b.current_published_revision_id is distinct from r.id
   or r.publication_status<>'published' or r.validation_status<>'ok' or r.coverage_status<>'healthy'
   or not r.external_share_allowed or not r.external_qa_passed
   or coalesce(s.qa_payload->>'public_body_ready','')<>'true'
   or coalesce(s.qa_payload->>'internal_body_ready','')<>'true'
 ) limit 1
$$;
revoke all on function public.hwarang_register_combined_share(text,uuid,uuid[],jsonb),public.hwarang_read_public_briefing(text),public.hwarang_publish_briefing(uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.hwarang_register_combined_share(text,uuid,uuid[],jsonb),public.hwarang_read_public_briefing(text),public.hwarang_publish_briefing(uuid,uuid,uuid) to service_role;
commit;
