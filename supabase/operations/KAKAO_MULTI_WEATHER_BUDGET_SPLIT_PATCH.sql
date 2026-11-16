-- Split external weather-fetch allocation; cache reads are free of allocation usage.
-- Preserve the existing shared total and all history. Initial test allocation is zero.
begin;
alter table public.kakao_weather_controls add column normal_daily_attempt_budget integer,add column test_daily_attempt_budget integer not null default 0;
update public.kakao_weather_controls set normal_daily_attempt_budget=daily_attempt_budget;
alter table public.kakao_weather_controls alter column normal_daily_attempt_budget set not null;
alter table public.kakao_weather_controls add constraint kakao_weather_split_budget_check check(normal_daily_attempt_budget>=0 and test_daily_attempt_budget>=0 and normal_daily_attempt_budget+test_daily_attempt_budget<=daily_attempt_budget);
alter table public.kakao_weather_usage add column test_attempts integer not null default 0 check(test_attempts>=0 and test_attempts<=attempts);
-- Prior attempts have no source provenance, so conservatively count as normal.
-- A failed fetch can cool down this shared cache for five minutes; a lease lasts 30 seconds.
-- Protect only same-grid imminent normal deliveries, not test messages or cache hits.
create function private.kakao_weather_normal_priority(p_nx integer,p_ny integer,p_at timestamptz) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_preferences p
 join public.kakao_multi_connections c using(owner_id)
 join public.kakao_weather_regions r on r.region_key=p.weather_region_key
 cross join lateral (values((p_at at time zone 'Asia/Seoul')::date-1),((p_at at time zone 'Asia/Seoul')::date),((p_at at time zone 'Asia/Seoul')::date+1)) dates(day)
 left join public.kakao_multi_batches b on b.owner_id=p.owner_id and b.day=dates.day
 where r.nx=p_nx and r.ny=p_ny and r.enabled and r.verified_at is not null and r.forecast_code is not null
 and p.enabled and not p.admin_paused and c.status='connected' and c.talk_message_granted
 and private.kakao_service_owner_active(p.owner_id) and not private.kakao_service_legacy_conflict(c.account_id)
 and extract(dow from dates.day)::integer=any(p.days)
 and (b.id is null or (b.completed_at is null and b.status in ('reserved','sending','held')))
 and p_at>=((dates.day+p.delivery_time) at time zone 'Asia/Seoul')-interval '6 minutes'
 and p_at<((dates.day+p.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes')
$$;
create function private.kakao_weather_claim_kind(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text,p_kind text) returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.kakao_weather_regions;c public.kakao_weather_cache;ctl public.kakao_weather_controls;u public.kakao_weather_usage;token uuid;at_time timestamptz:=clock_timestamp();kst date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
begin
 if p_kind is null or p_kind not in ('normal','test') or not private.kakao_weather_request_valid(p_forecast_day,p_base_date,p_base_time) then return jsonb_build_object('status','unavailable');end if;
 select * into r from public.kakao_weather_regions where region_key=p_region_key and enabled and verified_at is not null and forecast_code is not null;
 if not found then return jsonb_build_object('status','unavailable');end if;
 select * into ctl from public.kakao_weather_controls where singleton for update;
 if not found then return jsonb_build_object('status','unavailable');end if;
 insert into public.kakao_weather_cache(nx,ny,forecast_day,base_date,base_time) values(r.nx,r.ny,p_forecast_day,p_base_date,p_base_time) on conflict do nothing;
 select * into c from public.kakao_weather_cache where nx=r.nx and ny=r.ny and forecast_day=p_forecast_day and base_date=p_base_date and base_time=p_base_time for update;
 if c.forecast is not null and c.forecast->>'status'='ok' and c.forecast->>'day'=p_forecast_day::text and c.expires_at>at_time then return jsonb_build_object('status','cached','forecast',c.forecast,'region_name',r.label,'forecast_code',r.forecast_code);end if;
 if p_kind='test' and private.kakao_weather_normal_priority(r.nx,r.ny,at_time) then return jsonb_build_object('status','unavailable','region_name',r.label);end if;
 if c.lease_until>at_time or c.retry_after>at_time then return jsonb_build_object('status','wait');end if;
 insert into public.kakao_weather_usage(day,attempts) values(kst,0) on conflict do nothing;
 select * into u from public.kakao_weather_usage where day=kst for update;
 if u.attempts>=ctl.daily_attempt_budget or (p_kind='test' and u.test_attempts>=ctl.test_daily_attempt_budget) or (p_kind='normal' and u.attempts-u.test_attempts>=ctl.normal_daily_attempt_budget) then return jsonb_build_object('status','unavailable');end if;
 update public.kakao_weather_usage set attempts=attempts+1,test_attempts=test_attempts+case when p_kind='test' then 1 else 0 end where day=kst;
 token:=gen_random_uuid();
 update public.kakao_weather_cache set forecast=null,lease_token=token,lease_until=at_time+interval '30 seconds',retry_after=null where nx=r.nx and ny=r.ny and forecast_day=p_forecast_day and base_date=p_base_date and base_time=p_base_time;
 return jsonb_build_object('status','fetch','lease_token',token,'nx',r.nx,'ny',r.ny,'region_name',r.label,'forecast_code',r.forecast_code);
end $$;
create or replace function private.kakao_service_weather_claim(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text) returns jsonb language sql security definer set search_path='' as $$select private.kakao_weather_claim_kind(p_region_key,p_forecast_day,p_base_date,p_base_time,'normal')$$;
create or replace function private.kakao_test_weather_claim(p_id uuid,p_claim_token uuid,p_base_date text,p_base_time text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;region text;
begin
 if not private.kakao_test_validate(p_id,p_claim_token) then return jsonb_build_object('status','unavailable');end if;
 select * into t from public.kakao_multi_test_requests where id=p_id and claim_token=p_claim_token;
 if not found then return jsonb_build_object('status','unavailable');end if;
 select weather_region_key into region from public.kakao_multi_preferences where owner_id=t.owner_id;
 return private.kakao_weather_claim_kind(region,t.day,p_base_date,p_base_time,'test');
end $$;
revoke all on function private.kakao_weather_normal_priority(integer,integer,timestamptz),private.kakao_weather_claim_kind(text,date,text,text,text) from public,anon,authenticated,service_role;
commit;
