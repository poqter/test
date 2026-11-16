-- LOCAL DRAFT ONLY. HTML reuse pending policy review; no request budget enabled.
begin;
do $$begin
 if exists(select 1 from public.kakao_multi_preferences where weather_region_key is not null) then raise exception 'Region transition requires explicit subscriber migration';end if;
 if exists(select 1 from public.kakao_weather_cache) then raise exception 'Region transition requires reviewed cache retirement';end if;
end $$;
alter table public.kakao_weather_regions add column if not exists forecast_code text check(forecast_code ~ '^[0-9]{10}$');
update public.kakao_weather_regions set enabled=false;
-- Region selection reused from existing WORKSPACE; grids validated against official KMA catalog.
insert into public.kakao_weather_regions(region_key,label,nx,ny,enabled,verified_at,forecast_code) values
('web:1100000000','서울특별시',60,127,true,clock_timestamp(),'1100000000'),
('web:5100000000','강원특별자치도',73,134,true,clock_timestamp(),'5111000000'),
('web:4100000000','경기도',61,121,true,clock_timestamp(),'4111500000'),
('web:4800000000','경상남도',91,76,true,clock_timestamp(),'4812300000'),
('web:4700000000','경상북도',91,106,true,clock_timestamp(),'4717000000'),
('web:2700000000','대구광역시',89,90,true,clock_timestamp(),'2700000000'),
('web:3000000000','대전광역시',67,100,true,clock_timestamp(),'3000000000'),
('web:2600000000','부산광역시',98,76,true,clock_timestamp(),'2600000000'),
('web:3600000000','세종특별자치시',66,103,true,clock_timestamp(),'3611000000'),
('web:3100000000','울산광역시',102,84,true,clock_timestamp(),'3100000000'),
('web:2800000000','인천광역시',55,124,true,clock_timestamp(),'2800000000'),
('web:1200000000','전남광주통합특별시',60,74,true,clock_timestamp(),'1221000000'),
('web:5200000000','전북특별자치도',63,89,true,clock_timestamp(),'5211100000'),
('web:5000000000','제주특별자치도',53,38,true,clock_timestamp(),'5011000000'),
('web:4400000000','충청남도',55,106,true,clock_timestamp(),'4480000000'),
('web:4300000000','충청북도',69,106,true,clock_timestamp(),'4311100000')
on conflict(region_key) do update set label=excluded.label,nx=excluded.nx,ny=excluded.ny,enabled=true,verified_at=excluded.verified_at,forecast_code=excluded.forecast_code;
create or replace function private.kakao_service_weather_claim(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text) returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.kakao_weather_regions;c public.kakao_weather_cache;budget integer;used integer;token uuid;at_time timestamptz:=clock_timestamp();kst date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
begin
 if not private.kakao_weather_request_valid(p_forecast_day,p_base_date,p_base_time) then return jsonb_build_object('status','unavailable');end if;
 select * into r from public.kakao_weather_regions where region_key=p_region_key and enabled and verified_at is not null and forecast_code is not null;
 if not found then return jsonb_build_object('status','unavailable');end if;
 select daily_attempt_budget into budget from public.kakao_weather_controls where singleton for update;
 if not found or budget<=0 then return jsonb_build_object('status','unavailable');end if;
 insert into public.kakao_weather_cache(nx,ny,forecast_day,base_date,base_time) values(r.nx,r.ny,p_forecast_day,p_base_date,p_base_time) on conflict do nothing;
 select * into c from public.kakao_weather_cache where nx=r.nx and ny=r.ny and forecast_day=p_forecast_day and base_date=p_base_date and base_time=p_base_time for update;
 if c.forecast is not null and c.expires_at>at_time then return jsonb_build_object('status','cached','forecast',c.forecast,'region_name',r.label,'forecast_code',r.forecast_code);end if;
 if c.lease_until>at_time or c.retry_after>at_time then return jsonb_build_object('status','wait');end if;
 insert into public.kakao_weather_usage(day,attempts) values(kst,0) on conflict do nothing;
 select attempts into used from public.kakao_weather_usage where day=kst for update;
 if used>=budget then return jsonb_build_object('status','unavailable');end if;
 update public.kakao_weather_usage set attempts=attempts+1 where day=kst;
 token:=gen_random_uuid();
 update public.kakao_weather_cache set forecast=null,lease_token=token,lease_until=at_time+interval '30 seconds',retry_after=null where nx=r.nx and ny=r.ny and forecast_day=p_forecast_day and base_date=p_base_date and base_time=p_base_time;
 return jsonb_build_object('status','fetch','lease_token',token,'nx',r.nx,'ny',r.ny,'region_name',r.label,'forecast_code',r.forecast_code);
end $$;
create or replace function private.kakao_service_weather_complete(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text,p_lease_token uuid,p_forecast jsonb) returns boolean language plpgsql security definer set search_path='' as $$
declare r public.kakao_weather_regions;valid boolean:=false;at_time timestamptz:=clock_timestamp();
begin
 select * into r from public.kakao_weather_regions where region_key=p_region_key and enabled and verified_at is not null and forecast_code is not null;
 if not found or p_lease_token is null then return false;end if;
 if p_forecast is not null then
  begin
   valid:=jsonb_typeof(p_forecast)='object' and length(p_forecast::text)<=1024
   and (select count(*) from jsonb_object_keys(p_forecast))=8
   and p_forecast ?& array['status','day','low','high','morning','afternoon','issued_day','issued_time']
   and p_forecast->>'status'='ok' and p_forecast->>'day'=p_forecast_day::text
   and p_forecast->>'issued_day' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
   and p_forecast->>'issued_time' ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
   and ((p_forecast->>'issued_day')::date+(p_forecast->>'issued_time')::time) at time zone 'Asia/Seoul' between at_time-interval '24 hours' and at_time+interval '15 minutes'
   and jsonb_typeof(p_forecast->'morning')='string' and jsonb_typeof(p_forecast->'afternoon')='string'
   and length(p_forecast->>'morning')<=40 and length(p_forecast->>'afternoon')<=40
   and p_forecast->>'morning' ~ '^[가-힣[:space:]·/(),~\-]*$' and p_forecast->>'afternoon' ~ '^[가-힣[:space:]·/(),~\-]*$'
   and length(btrim((p_forecast->>'morning')||(p_forecast->>'afternoon')))>0
   and (p_forecast->'low'='null'::jsonb or (jsonb_typeof(p_forecast->'low')='number' and (p_forecast->>'low')::numeric between -60 and 60))
   and (p_forecast->'high'='null'::jsonb or (jsonb_typeof(p_forecast->'high')='number' and (p_forecast->>'high')::numeric between -60 and 60))
   and (p_forecast->'low'='null'::jsonb or p_forecast->'high'='null'::jsonb or (p_forecast->>'low')::numeric<=(p_forecast->>'high')::numeric);
  exception when others then valid:=false;end;
 end if;
 update public.kakao_weather_cache set forecast=case when valid then p_forecast end,
 expires_at=case when valid then least(((p_forecast_day+1)::timestamp at time zone 'Asia/Seoul'),at_time+interval '15 minutes') end,
 retry_after=case when not coalesce(valid,false) then at_time+interval '5 minutes' end,lease_token=null,lease_until=null
 where nx=r.nx and ny=r.ny and forecast_day=p_forecast_day and base_date=p_base_date and base_time=p_base_time and lease_token=p_lease_token and lease_until>at_time;
 return found and (p_forecast is null or coalesce(valid,false));
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
