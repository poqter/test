-- LOCAL DRAFT ONLY. No catalog seed or guessed coordinates.
begin;
create table public.kakao_weather_regions (
 forecast_code text check(forecast_code ~ '^[0-9]{10}$'),
 region_key text primary key check(length(region_key) between 1 and 80), label text not null check(length(label) between 1 and 100),
 nx integer not null check(nx between 1 and 149),ny integer not null check(ny between 1 and 253),
 enabled boolean not null default false,verified_at timestamptz
);
alter table public.kakao_weather_regions enable row level security;
revoke all on public.kakao_weather_regions from public,anon,authenticated;
grant select,insert,update,delete on public.kakao_weather_regions to service_role;
alter table public.kakao_multi_preferences add column weather_region_key text references public.kakao_weather_regions(region_key);
create or replace function private.kakao_weather_region_valid(p_key text) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_weather_regions where region_key=p_key and enabled and verified_at is not null)
$$;
create or replace function private.kakao_weather_regions() returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
 perform private.kakao_require_user();
 return (select coalesce(jsonb_agg(jsonb_build_object('region_key',region_key,'display_name',label) order by label,region_key),'[]'::jsonb) from public.kakao_weather_regions where enabled and verified_at is not null);
end $$;
create or replace function private.kakao_save_weather_region(p_region_key text) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); previous text;
begin
 if p_region_key is not null and not private.kakao_weather_region_valid(p_region_key) then raise exception 'Invalid weather region'; end if;
 perform 1 from public.kakao_multi_connections where owner_id=u for update;
 if not found then raise exception 'Connect first'; end if;
 select weather_region_key into previous from public.kakao_multi_preferences where owner_id=u;
 insert into public.kakao_multi_preferences(owner_id,weather_region_key) values(u,p_region_key)
 on conflict(owner_id) do update set weather_region_key=excluded.weather_region_key,
 enabled=case when p_region_key is null then false else kakao_multi_preferences.enabled end,updated_at=clock_timestamp();
 if previous is distinct from p_region_key then
  update public.kakao_multi_jobs set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp() where owner_id=u and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp() where owner_id=u and status in ('reserved','held');
 end if;
 return private.kakao_my_status();
end $$;
create or replace function public.kakao_weather_regions() returns jsonb language sql security invoker set search_path='' as $$select private.kakao_weather_regions()$$;
create or replace function public.kakao_save_weather_region(p_region_key text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_save_weather_region(p_region_key)$$;
revoke all on function private.kakao_weather_region_valid(text) from public,anon,authenticated;
grant execute on function private.kakao_weather_region_valid(text) to service_role;
revoke all on function private.kakao_weather_regions(),public.kakao_weather_regions(),private.kakao_save_weather_region(text),public.kakao_save_weather_region(text) from public,anon;
grant execute on function private.kakao_weather_regions(),public.kakao_weather_regions(),private.kakao_save_weather_region(text),public.kakao_save_weather_region(text) to authenticated;
create or replace function private.kakao_my_status() returns jsonb language plpgsql volatile security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 -- Authenticated owner's abandoned confirmation expires even when delivery gate is OFF.
 update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,
 confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=clock_timestamp()
 where owner_id=u and status='pending_confirmation' and confirmation_expires_at<=clock_timestamp();
 if found then update public.kakao_multi_preferences set enabled=false,updated_at=clock_timestamp() where owner_id=u; end if;
 update public.kakao_multi_oauth set ticket_hash=null,state_hash=null,browser_hash=null,
 status=case when status='consumed' then 'consumed' else 'cancelled' end
 where owner_id=u and expires_at<=clock_timestamp() and (ticket_hash is not null or state_hash is not null or browser_hash is not null);
 select jsonb_build_object('dispatch_ready',coalesce((private.kakao_service_gate()->>'enabled')::boolean,false),'connection_status',coalesce(c.status,'disconnected'),
 'enabled',coalesce(p.enabled,false),'time',coalesce(left(p.delivery_time::text,5),'08:00'),
 'weather_region_key',p.weather_region_key,'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,'accepted_parts',coalesce(j.accepted_parts,0),'total_parts',coalesce(j.total_parts,0),
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id and z.status='accepted') accepted_parts,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id) total_parts from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=u order by b.day desc,b.created_at desc limit 1) j on true;
 return result;
end $$;
create or replace function private.kakao_save_preferences(p_enabled boolean,p_time text,p_days integer[],p_send_empty boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); c public.kakao_multi_connections;
begin
 if p_enabled is null or p_send_empty is null or p_time is null or p_time !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
 or p_days is null or cardinality(p_days) not between 1 and 7 or not p_days <@ array[0,1,2,3,4,5,6] or array_position(p_days,null) is not null then raise exception 'Invalid preferences'; end if;
 select * into c from public.kakao_multi_connections where owner_id=u for update;
 if not found then raise exception 'Connect first'; end if;
 if p_enabled and (private.kakao_service_excluded_owner(u) or c.status<>'connected' or not c.talk_message_granted) then raise exception 'Reconnect required'; end if;
 if p_enabled and not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=u and private.kakao_weather_region_valid(p.weather_region_key)) then raise exception 'Select weather region first'; end if;
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time,days,send_empty)
 values(u,p_enabled,p_time::time,array(select distinct d from unnest(p_days) d order by d),p_send_empty)
 on conflict(owner_id) do update set enabled=excluded.enabled,delivery_time=excluded.delivery_time,days=excluded.days,send_empty=excluded.send_empty,updated_at=now();
 if not p_enabled then
  update public.kakao_multi_jobs set status='cancelled',outcome='paused',completed_at=now() where owner_id=u and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='paused',completed_at=now() where owner_id=u and status in ('reserved','held');
 end if;
 return private.kakao_my_status();
end $$;
create or replace function private.kakao_service_snapshot(p_owner uuid,p_day date) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object(
 'identity',jsonb_build_object('owner_id',me.id,'unit',me.organization_unit_id,'position',me.position_code,'role',me.role),
 'preferences',(select jsonb_build_object('time',p.delivery_time,'days',p.days,'send_empty',p.send_empty,'enabled',p.enabled,'weather_region_key',p.weather_region_key,'weather_catalog',(select jsonb_build_object('nx',r.nx,'ny',r.ny,'forecast_code',r.forecast_code,'enabled',r.enabled,'verified_at',r.verified_at) from public.kakao_weather_regions r where r.region_key=p.weather_region_key)) from public.kakao_multi_preferences p where p.owner_id=me.id),
 'empty_explicit',exists(select 1 from public.sales_empty_days x where x.owner=me.id and x.day=p_day),
 'events',coalesce((select jsonb_agg(jsonb_build_object(
 'id',e.id,'day',e.day,'start_time',e.start_time,'time_pending',e.time_pending,'title',e.title,'kind',e.kind,'status',e.status,
 'own',e.owner=me.id,'companion',e.companion=me.id,'common',e.common,
 'end_time',case when e.owner=me.id then e.end_time end,'place',case when e.owner=me.id then e.place end)
 order by e.start_time nulls last,e.id)
 from public.sales_events e join public.profiles author on author.id=e.owner
 where e.unit=me.organization_unit_id and author.organization_unit_id=me.organization_unit_id and author.is_active
 and e.day=p_day and e.deleted_at is null and (e.owner=me.id or e.companion=me.id or e.common)),'[]'::jsonb))
 from public.profiles me where me.id=p_owner and private.kakao_service_owner_active(p_owner)
$$;
commit;
