begin;
create table public.hwarang_share_content (
 id text primary key check(id ~ '^[a-f0-9]{64}$'), packet jsonb not null, html_template text not null, created_at timestamptz not null default now());
create table public.hwarang_share_weather (
 id text primary key check(id ~ '^[a-f0-9]{64}$'), payload jsonb not null, rendered_html text not null, created_at timestamptz not null default now());
create table public.hwarang_share_previews (
 id text primary key check(id ~ '^[a-f0-9]{64}$'), state text not null default 'active' check(state in ('active','deleting')),
 touched_at timestamptz not null default now());
create table public.hwarang_share_retention_status (
 id boolean primary key default true check(id), last_started_at timestamptz, last_finished_at timestamptz,
 last_success_at timestamptz, status text not null default 'never', counts jsonb not null default '{}'::jsonb);
insert into public.hwarang_share_retention_status(id) values(true);
alter table public.hwarang_share_content enable row level security;
revoke all on public.hwarang_share_content from public,anon,authenticated;
grant select,insert,update,delete on public.hwarang_share_content to service_role;
alter table public.hwarang_share_weather enable row level security;
revoke all on public.hwarang_share_weather from public,anon,authenticated;
grant select,insert,update,delete on public.hwarang_share_weather to service_role;
alter table public.hwarang_share_previews enable row level security;
revoke all on public.hwarang_share_previews from public,anon,authenticated;
grant select,insert,update,delete on public.hwarang_share_previews to service_role;
alter table public.hwarang_share_retention_status enable row level security;
revoke all on public.hwarang_share_retention_status from public,anon,authenticated;
grant select,insert,update,delete on public.hwarang_share_retention_status to service_role;
alter table public.hwarang_briefing_public_shares
 add column content_id text references public.hwarang_share_content(id),
 add column weather_id text references public.hwarang_share_weather(id),
 add column preview_id text references public.hwarang_share_previews(id),
 add column reuse_key text;
alter table public.hwarang_briefing_public_shares alter column expires_at set default now()+interval '7 days';
create index hwarang_share_content_ref on public.hwarang_briefing_public_shares(content_id);
create index hwarang_share_weather_ref on public.hwarang_briefing_public_shares(weather_id);
create index hwarang_share_preview_ref on public.hwarang_briefing_public_shares(preview_id);
create index hwarang_share_key_ref on public.hwarang_briefing_public_shares(sender_user_id,reuse_key,expires_at) where revoked_at is null;

create function public.hwarang_html_escape(v text) returns text language sql immutable set search_path='' as $$
 select replace(replace(replace(replace(replace(coalesce(v,''),'&','&amp;'),'<','&lt;'),'>','&gt;'),'"','&quot;'),'''','&#x27;');
$$;

create function public.hwarang_expand_share(p_token text) returns jsonb language sql stable security invoker set search_path='' as $$
 select case when s.content_id is null then s.public_packet else
 c.packet || jsonb_build_object('sender',s.public_packet->'sender','storage_version',4,
 'asset_version',left(s.preview_id,24),'preview_path','shared/'||s.preview_id||'/preview.png',
 'body',(c.packet->'body') || case when w.payload='{}'::jsonb then '{}'::jsonb else jsonb_build_object('weather_forecast',w.payload) end,
 'rendered_html',replace(replace(replace(c.html_template,
 '__HW_WEATHER_9e21__',w.rendered_html),'__HW_TOKEN_9e21__',s.token),
 '__HW_IDENTITY_9e21__',public.hwarang_html_escape(concat_ws(' ',s.public_packet->'sender'->>'name',s.public_packet->'sender'->>'position')))) end
 from public.hwarang_briefing_public_shares s
 left join public.hwarang_share_content c on c.id=s.content_id
 left join public.hwarang_share_weather w on w.id=s.weather_id where s.token=p_token;
$$;
create function public.hwarang_find_shared_link(p_sender uuid,p_key text) returns text language sql stable security invoker set search_path='' as $$
 select token from public.hwarang_briefing_public_shares where sender_user_id=p_sender and reuse_key=p_key
 and revoked_at is null and expires_at>now() order by created_at,token limit 1;
$$;
create function public.hwarang_prepare_preview(p_id text) returns boolean language plpgsql security invoker set search_path='' as $$
begin
 insert into public.hwarang_share_previews(id) values(p_id) on conflict(id) do update set touched_at=now()
 where hwarang_share_previews.state='active';
 if not found then raise exception 'Preview cleanup in progress. Retry shortly.'; end if;
 return true;
end $$;
create function public.hwarang_register_shared_link(p_token text,p_sender uuid,p_revisions uuid[],p_packet jsonb,p_parts jsonb)
returns text language plpgsql security invoker set search_path='' as $$
declare existing text;
begin
 perform pg_advisory_xact_lock(hashtextextended(p_sender::text||(p_parts->>'reuse_key'),0));
 existing=public.hwarang_find_shared_link(p_sender,p_parts->>'reuse_key');
 if existing is not null then return existing; end if;
 perform 1 from public.hwarang_share_previews where id=p_parts->>'preview_id' and state='active' for update;
 if not found then raise exception 'Preview unavailable. Retry shortly.'; end if;
 insert into public.hwarang_share_content(id,packet,html_template)
 values(p_parts->>'content_id',p_parts->'content'->'packet',p_parts->'content'->>'html_template') on conflict do nothing;
 insert into public.hwarang_share_weather(id,payload,rendered_html)
 values(p_parts->>'weather_id',p_parts->'weather'->'payload',p_parts->'weather'->>'rendered_html') on conflict do nothing;
 -- Reuse established server validation before replacing the temporary full packet.
 perform public.hwarang_register_combined_share(p_token,p_sender,p_revisions,p_packet);
 update public.hwarang_briefing_public_shares set content_id=p_parts->>'content_id',weather_id=p_parts->>'weather_id',
 preview_id=p_parts->>'preview_id',reuse_key=p_parts->>'reuse_key',
 public_packet=jsonb_build_object('schema','hwarang-share-v3','storage_version',4,'sender',p_packet->'sender')
 where token=p_token;
 return p_token;
end $$;

-- A newer published pointer does not invalidate an already shared morning edition.
create or replace function public.hwarang_read_public_briefing(p_token text)
returns jsonb language sql stable security definer set search_path='' as $$
 select public.hwarang_expand_share(s.token) from public.hwarang_briefing_public_shares s
 join public.hwarang_briefing_operating_policy op on op.policy_key='WORKSPACE' and op.external_sharing_approved
 join public.profiles u on u.id=s.sender_user_id and u.is_active
 where s.token=p_token and s.revoked_at is null and s.expires_at>now() and p_token ~ '^[A-Za-z0-9_-]{32,64}$'
 and not exists(select 1 from (
 select s.revision_id union select c.revision_id from public.hwarang_briefing_share_components c where c.token=s.token) x
 left join public.hwarang_briefing_revisions r on r.id=x.revision_id
 where r.id is null or r.publication_status='hidden' or not r.external_share_allowed or not r.external_qa_passed) limit 1;
$$;
-- Disable the old mutation endpoint as well as the application refresh path.
create or replace function public.hwarang_refresh_briefing_share(p_token text,p_old uuid,p_new uuid,p_packet jsonb)
returns boolean language sql security invoker set search_path='' as $$ select false; $$;

create function public.hwarang_collect_shared_garbage() returns jsonb language plpgsql security definer set search_path='' as $$
declare paths jsonb;
begin
 delete from public.hwarang_share_content c where c.created_at<now()-interval '1 day'
 and not exists(select 1 from public.hwarang_briefing_public_shares s where s.content_id=c.id);
 delete from public.hwarang_share_weather w where w.created_at<now()-interval '1 day'
 and not exists(select 1 from public.hwarang_briefing_public_shares s where s.weather_id=w.id);
 -- Claim before Storage I/O: creators cannot attach a preview being deleted.
 with claimed as (update public.hwarang_share_previews p set state='deleting'
 where (p.state='deleting' or p.touched_at<now()-interval '1 day')
 and not exists(select 1 from public.hwarang_briefing_public_shares s where s.preview_id=p.id)
 returning p.id) select coalesce(jsonb_agg('shared/'||id||'/preview.png'),'[]'::jsonb) into paths from claimed;
 return paths;
end $$;
create function public.hwarang_finish_preview_cleanup() returns bigint language plpgsql security definer set search_path='' as $$
declare n bigint;
begin
 delete from public.hwarang_share_previews p where state='deleting'
 and not exists(select 1 from storage.objects o where o.bucket_id='briefing-share-assets' and o.name='shared/'||p.id||'/preview.png')
 and not exists(select 1 from public.hwarang_briefing_public_shares s where s.preview_id=p.id);
 get diagnostics n=row_count;return n;
end $$;
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
   and split_part(name,'/',1)<>'shared'
   and created_at<=now()-interval '37 days'
   and not exists(select 1 from public.hwarang_briefing_public_shares s where s.token=split_part(o.name,'/',1))
   order by created_at limit 1000) o),'[]'::jsonb));
$$;
revoke all on function public.hwarang_html_escape(text) from public,anon,authenticated;
grant execute on function public.hwarang_html_escape(text) to service_role;
revoke all on function public.hwarang_expand_share(text) from public,anon,authenticated;
grant execute on function public.hwarang_expand_share(text) to service_role;
revoke all on function public.hwarang_find_shared_link(uuid,text) from public,anon,authenticated;
grant execute on function public.hwarang_find_shared_link(uuid,text) to service_role;
revoke all on function public.hwarang_prepare_preview(text) from public,anon,authenticated;
grant execute on function public.hwarang_prepare_preview(text) to service_role;
revoke all on function public.hwarang_register_shared_link(text,uuid,uuid[],jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.hwarang_register_shared_link(text,uuid,uuid[],jsonb,jsonb) to service_role;
revoke all on function public.hwarang_collect_shared_garbage() from public,anon,authenticated;
grant execute on function public.hwarang_collect_shared_garbage() to service_role;
revoke all on function public.hwarang_finish_preview_cleanup() from public,anon,authenticated;
grant execute on function public.hwarang_finish_preview_cleanup() to service_role;
commit;

