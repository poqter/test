begin;
set local role service_role;
do $$
declare s public.hwarang_briefing_public_shares%rowtype; p jsonb; parts jsonb; ids uuid[];
 t text=md5(random()::text); t2 text=md5(random()::text); cid text=repeat(md5(random()::text),2);
 wid text=repeat(md5(random()::text),2); pid text=repeat(md5(random()::text),2); k text=repeat(md5(random()::text),2);
 result text; expanded jsonb; expiry timestamptz;
begin
 select * into strict s from public.hwarang_briefing_public_shares where content_id is null
 and public_packet ? 'components' order by created_at desc limit 1;
 p=jsonb_set(s.public_packet,'{sender}', '{"name":"<검증>&","position":"팀장"}'::jsonb);
 select array_agg((x->>'revision_id')::uuid) into ids from jsonb_array_elements(p->'components') x;
 parts=jsonb_build_object('content_id',cid,'weather_id',wid,'preview_id',pid,'reuse_key',k,
 'content',jsonb_build_object('packet',p-'sender'-'rendered_html'-'asset_version',
 'html_template','<header>__HW_IDENTITY_9e21__</header><main>__HW_WEATHER_9e21__</main><a href="?token=__HW_TOKEN_9e21__">읽기</a>'),
 'weather',jsonb_build_object('payload','{}'::jsonb,'rendered_html',''));
 perform public.hwarang_prepare_preview(pid);
 result=public.hwarang_register_shared_link(t,s.sender_user_id,ids,p,parts);
 if result<>t then raise exception 'registration'; end if;
 result=public.hwarang_register_shared_link(t2,s.sender_user_id,ids,p,parts);
 if result<>t then raise exception 'duplicate'; end if;
 select expires_at into expiry from public.hwarang_briefing_public_shares where token=t;
 if expiry<>now()+interval '7 days' then raise exception 'new lifetime'; end if;
 if (select expires_at from public.hwarang_briefing_public_shares where token=s.token)<>s.expires_at then raise exception 'old lifetime changed'; end if;
 if (select public_packet ? 'body' from public.hwarang_briefing_public_shares where token=t) then raise exception 'body copied'; end if;
 expanded=public.hwarang_read_public_briefing(t);
 if expanded is null or expanded->'sender'<>p->'sender' or expanded->>'preview_path'<>'shared/'||pid||'/preview.png'
 or position('&lt;검증&gt;&amp;' in expanded->>'rendered_html')=0 or position(t in expanded->>'rendered_html')=0 then raise exception 'hydration'; end if;
 -- Publishing a newer pointer must not invalidate or rewrite an old link.
 update public.hwarang_briefings set current_published_revision_id=null where id in
 (select briefing_id from public.hwarang_briefing_revisions where id=any(ids));
 if public.hwarang_read_public_briefing(t) is null then raise exception 'snapshot invalidated'; end if;
 if public.hwarang_refresh_briefing_share(t,ids[1],ids[1],p) then raise exception 'snapshot mutable'; end if;
 update public.hwarang_share_previews set touched_at=now()-interval '2 days' where id=pid;
 perform public.hwarang_collect_shared_garbage();
 if (select state from public.hwarang_share_previews where id=pid)<>'active' then raise exception 'referenced preview claimed'; end if;
 update public.hwarang_briefing_public_shares set revoked_at=now() where token=t;
 if public.hwarang_read_public_briefing(t) is not null then raise exception 'revocation ignored'; end if;
 update public.hwarang_briefing_public_shares set expires_at=now()-interval '6 days' where token=t;
 if public.hwarang_finish_share_cleanup(t) then raise exception 'grace period'; end if;
 update public.hwarang_briefing_public_shares set expires_at=now()-interval '7 days' where token=t;
 if not public.hwarang_finish_share_cleanup(t) then raise exception 'cleanup'; end if;
 perform public.hwarang_collect_shared_garbage();
 if (select state from public.hwarang_share_previews where id=pid)<>'deleting' then raise exception 'unused preview not claimed'; end if;
 begin
  perform public.hwarang_prepare_preview(pid);
  raise exception 'deleting preview reused';
 exception when raise_exception then
  if sqlerrm not like 'Preview cleanup%' then raise; end if;
 end;
 if has_function_privilege('anon','public.hwarang_expand_share(text)','execute') then raise exception 'public raw read'; end if;
end $$;
rollback;
select 'shared content checks passed' as result;
