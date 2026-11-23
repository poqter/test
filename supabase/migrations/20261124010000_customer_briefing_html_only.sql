begin;
create or replace function public.hwarang_expand_share(p_token text) returns jsonb language sql stable security invoker set search_path='' as $$
 select case when s.content_id is null then s.public_packet else
 c.packet || jsonb_build_object('sender',s.public_packet->'sender','storage_version',4,
 'asset_version',left(s.content_id,24),
 'body',(c.packet->'body') || case when w.payload='{}'::jsonb then '{}'::jsonb else jsonb_build_object('weather_forecast',w.payload) end,
 'rendered_html',replace(replace(replace(c.html_template,
 '__HW_WEATHER_9e21__',w.rendered_html),'__HW_TOKEN_9e21__',s.token),
 '__HW_IDENTITY_9e21__',public.hwarang_html_escape(concat_ws(' ',s.public_packet->'sender'->>'name',s.public_packet->'sender'->>'position')))) end
 from public.hwarang_briefing_public_shares s
 left join public.hwarang_share_content c on c.id=s.content_id
 left join public.hwarang_share_weather w on w.id=s.weather_id where s.token=p_token;
$$;
create or replace function public.hwarang_register_shared_link(p_token text,p_sender uuid,p_revisions uuid[],p_packet jsonb,p_parts jsonb)
returns text language plpgsql security invoker set search_path='' as $$
declare existing text;
begin
 perform pg_advisory_xact_lock(hashtextextended(p_sender::text||(p_parts->>'reuse_key'),0));
 existing=public.hwarang_find_shared_link(p_sender,p_parts->>'reuse_key');
 if existing is not null then return existing; end if;
 insert into public.hwarang_share_content(id,packet,html_template)
 values(p_parts->>'content_id',p_parts->'content'->'packet',p_parts->'content'->>'html_template') on conflict do nothing;
 insert into public.hwarang_share_weather(id,payload,rendered_html)
 values(p_parts->>'weather_id',p_parts->'weather'->'payload',p_parts->'weather'->>'rendered_html') on conflict do nothing;
 -- Reuse established server validation before replacing the temporary full packet.
 perform public.hwarang_register_combined_share(p_token,p_sender,p_revisions,p_packet);
 update public.hwarang_briefing_public_shares set content_id=p_parts->>'content_id',weather_id=p_parts->>'weather_id',
 reuse_key=p_parts->>'reuse_key',
 public_packet=jsonb_build_object('schema','hwarang-share-v3','storage_version',4,'sender',p_packet->'sender')
 where token=p_token;
 return p_token;
end $$;

commit;
