begin;
-- Hash only customer-visible content and stable edition/settings metadata.
-- Applying the index also covers existing links without rewriting their packets.
create or replace function public.hwarang_share_identity(p jsonb)
returns text language sql immutable strict set search_path='' as $$
 select encode(sha256(convert_to(jsonb_build_object(
   'schema',p->'schema','reader_version',p->'reader_version',
   'selected_profiles',p->'selected_profiles','requested_date',p->'requested_date',
   'briefing_date',p->'briefing_date','sender',p->'sender','components',p->'components',
   'edition',p->'edition','body',(p->'body')-'weather_forecast',
   'weather',(select coalesce(jsonb_object_agg(k,v),'{}'::jsonb)
      from jsonb_each(coalesce(nullif(p->'body'->'weather_forecast','null'::jsonb),'{}'::jsonb)) w(k,v)
      where k=any(array['status','reason','region_code','region_name','date','condition','morning','afternoon','low','high','guidance']))
 )::text,'UTF8')),'hex');
$$;
create index if not exists hwarang_share_reuse_idx
 on public.hwarang_briefing_public_shares(sender_user_id,public.hwarang_share_identity(public_packet),expires_at)
 where revoked_at is null;
create index if not exists hwarang_share_expiry_idx on public.hwarang_briefing_public_shares(expires_at);

create or replace function public.hwarang_find_reusable_share(p_sender uuid,p_packet jsonb)
returns jsonb language sql security invoker set search_path='' as $$
 select jsonb_build_object('token',s.token,'public_packet',s.public_packet,'expires_at',s.expires_at)
 from public.hwarang_briefing_public_shares s
 where s.sender_user_id=p_sender and s.revoked_at is null and s.expires_at>now()
 and public.hwarang_share_identity(s.public_packet)=public.hwarang_share_identity(p_packet)
 order by s.created_at,s.token limit 1;
$$;

create or replace function public.hwarang_register_combined_share_once(p_token text,p_sender uuid,p_revisions uuid[],p_packet jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare result jsonb;
begin
 -- Serialize identical requests across servers; uploaded candidates remain private.
 perform pg_advisory_xact_lock(hashtextextended(p_sender::text||public.hwarang_share_identity(p_packet),0));
 result=public.hwarang_find_reusable_share(p_sender,p_packet);
 if result is not null then return result; end if;
 perform public.hwarang_register_combined_share(p_token,p_sender,p_revisions,p_packet);
 return public.hwarang_find_reusable_share(p_sender,p_packet);
end;
$$;

-- Only the server role may enumerate private Storage paths or finalize retention.
-- File bytes MUST be removed by the Storage API, never DELETE storage.objects.
create or replace function public.hwarang_share_cleanup_batch()
returns jsonb language sql security definer set search_path='' as $$
 select jsonb_build_object(
 'shares',coalesce((select jsonb_agg(jsonb_build_object('token',s.token,'paths',
   (select coalesce(jsonb_agg(o.name),'[]'::jsonb) from storage.objects o
    where o.bucket_id='briefing-share-assets' and split_part(o.name,'/',1)=s.token)))
   from (select token from public.hwarang_briefing_public_shares
         where expires_at<=now()-interval '7 days' order by expires_at limit 100) s),'[]'::jsonb),
 'orphans',coalesce((select jsonb_agg(o.name) from (
   select name from storage.objects o where bucket_id='briefing-share-assets'
   and created_at<=now()-interval '37 days'
   and not exists(select 1 from public.hwarang_briefing_public_shares s where s.token=split_part(o.name,'/',1))
   order by created_at limit 1000) o),'[]'::jsonb));
$$;
create or replace function public.hwarang_finish_share_cleanup(p_token text)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 delete from public.hwarang_briefing_public_shares s where s.token=p_token
 and s.expires_at<=now()-interval '7 days'
 and not exists(select 1 from storage.objects o
   where o.bucket_id='briefing-share-assets' and split_part(o.name,'/',1)=s.token);
 return found;
end;
$$;
revoke all on function public.hwarang_share_identity(jsonb) from public,anon,authenticated;
revoke all on function public.hwarang_find_reusable_share(uuid,jsonb) from public,anon,authenticated;
revoke all on function public.hwarang_register_combined_share_once(text,uuid,uuid[],jsonb) from public,anon,authenticated;
revoke all on function public.hwarang_share_cleanup_batch() from public,anon,authenticated;
revoke all on function public.hwarang_finish_share_cleanup(text) from public,anon,authenticated;
grant execute on function public.hwarang_share_identity(jsonb),public.hwarang_find_reusable_share(uuid,jsonb),
 public.hwarang_register_combined_share_once(text,uuid,uuid[],jsonb),public.hwarang_share_cleanup_batch(),
 public.hwarang_finish_share_cleanup(text) to service_role;
commit;
