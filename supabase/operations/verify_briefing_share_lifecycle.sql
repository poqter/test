-- Transactional verification: all fixtures and updates are rolled back.
begin;
do $$
declare s public.hwarang_briefing_public_shares%rowtype;
 p jsonb; q jsonb; a jsonb; b jsonb; ids uuid[]; t text; t2 text; n integer;
begin
 select * into strict s from public.hwarang_briefing_public_shares
 where public_packet->>'reader_version'='20261026-share-preview'
 and revoked_at is null and expires_at>now() order by created_at desc limit 1;
 p=s.public_packet;
 if public.hwarang_find_reusable_share(s.sender_user_id,p) is null then raise exception 'legacy link reuse failed'; end if;
 p=jsonb_set(p,'{body,weather_forecast}',coalesce(p->'body'->'weather_forecast','{}'::jsonb));
 q=jsonb_set(p,'{body,weather_forecast,issued_at}','"different issue time"');
 q=jsonb_set(q,'{body,weather_forecast,retrieved_at}','"different fetch time"');
 if public.hwarang_share_identity(p)<>public.hwarang_share_identity(q) then raise exception 'timestamp-only weather change'; end if;
 foreach t in array array['region_code','low','condition','guidance','status'] loop
  q=jsonb_set(p,array['body','weather_forecast',t],'"changed"');
  if public.hwarang_share_identity(p)=public.hwarang_share_identity(q) then raise exception 'weather change ignored: %',t; end if;
 end loop;
 foreach t in array array['sender','selected_profiles','requested_date','components','reader_version'] loop
  q=jsonb_set(p,array[t],'"changed"');
  if public.hwarang_share_identity(p)=public.hwarang_share_identity(q) then raise exception 'setting change ignored: %',t; end if;
 end loop;
 if public.hwarang_find_reusable_share('00000000-0000-0000-0000-000000000000',s.public_packet) is not null then raise exception 'cross-user reuse'; end if;
 if public.hwarang_finish_share_cleanup(s.token) then raise exception 'live share deleted'; end if;
 -- Exercise atomic registration twice, using a unique test-only identity.
 p=jsonb_set(s.public_packet,'{sender,name}',to_jsonb('retention-test-'||md5(random()::text)));
 select array_agg((x->>'revision_id')::uuid) into ids from jsonb_array_elements(p->'components') x;
 t=md5(random()::text);t2=md5(random()::text);
 a=public.hwarang_register_combined_share_once(t,s.sender_user_id,ids,p);
 b=public.hwarang_register_combined_share_once(t2,s.sender_user_id,ids,p);
 if a->>'token'<>t or b->>'token'<>t or a->>'expires_at'<>b->>'expires_at' then raise exception 'duplicate registration or extended expiry'; end if;
 update public.hwarang_briefing_public_shares set revoked_at=now() where token=t;
 if public.hwarang_find_reusable_share(s.sender_user_id,p) is not null then raise exception 'revoked reuse'; end if;
 update public.hwarang_briefing_public_shares set revoked_at=null,expires_at=now()-interval '1 day' where token=t;
 if public.hwarang_find_reusable_share(s.sender_user_id,p) is not null then raise exception 'expired reuse'; end if;
 if public.hwarang_finish_share_cleanup(t) then raise exception 'grace period ignored'; end if;
 update public.hwarang_briefing_public_shares set expires_at=now()-interval '7 days' where token=t;
 if not public.hwarang_finish_share_cleanup(t) then raise exception 'eligible row not deleted'; end if;
 if exists(select 1 from public.hwarang_briefing_share_components where token=t) then raise exception 'component cascade failed'; end if;
 -- Existing files prevent finalization, even for a share made eligible in this transaction.
 if exists(select 1 from storage.objects where bucket_id='briefing-share-assets' and split_part(name,'/',1)=s.token) then
  update public.hwarang_briefing_public_shares set expires_at=now()-interval '8 days' where token=s.token;
  if public.hwarang_finish_share_cleanup(s.token) then raise exception 'row deleted before files'; end if;
 end if;
 if has_function_privilege('anon','public.hwarang_share_cleanup_batch()','EXECUTE')
 or has_function_privilege('authenticated','public.hwarang_register_combined_share_once(text,uuid,uuid[],jsonb)','EXECUTE') then raise exception 'public lifecycle access'; end if;
end $$;
rollback;
select 'share lifecycle transaction checks passed' as result;
