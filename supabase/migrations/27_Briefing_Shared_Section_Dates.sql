begin;
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
  if not found or v_code=any(v_codes) then
   raise exception 'Component no longer shareable'; end if;
  if not exists(select 1 from jsonb_array_elements(p_packet->'body'->'sections') x
    where x->>'profile_code'=v_code and x->>'briefing_date'=v_date::text) then
    raise exception 'Section date mismatch'; end if;
  v_day=greatest(v_day,v_date);v_codes=array_append(v_codes,v_code);
 end loop;
 if coalesce(p_packet->>'briefing_date','')<>v_day::text then raise exception 'Edition date mismatch'; end if;
 insert into public.hwarang_briefing_public_shares(token,revision_id,sender_user_id,public_packet)
 values(p_token,p_revisions[1],p_sender,p_packet);
 insert into public.hwarang_briefing_share_components(token,revision_id) select p_token,unnest(p_revisions);
 return true;
end $$;


revoke all on function public.hwarang_register_combined_share(text,uuid,uuid[],jsonb) from public,anon,authenticated;
grant execute on function public.hwarang_register_combined_share(text,uuid,uuid[],jsonb) to service_role;
commit;
