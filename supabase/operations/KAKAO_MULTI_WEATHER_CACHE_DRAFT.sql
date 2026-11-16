-- LOCAL DRAFT ONLY. Apply after weather region schema. No network calls or credentials.
begin;
create table public.kakao_weather_controls(singleton boolean primary key default true check(singleton),daily_attempt_budget integer not null default 0 check(daily_attempt_budget between 0 and 1000));
insert into public.kakao_weather_controls default values;
create table public.kakao_weather_usage(day date primary key,attempts integer not null check(attempts between 0 and 1000));
create table public.kakao_weather_cache(
 nx integer not null,ny integer not null,forecast_day date not null,base_date text not null,base_time text not null,
 forecast jsonb,lease_token uuid,lease_until timestamptz,expires_at timestamptz,retry_after timestamptz,
 primary key(nx,ny,forecast_day,base_date,base_time)
);
do $$declare t text;begin
 foreach t in array array['kakao_weather_controls','kakao_weather_usage','kakao_weather_cache'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated',t);
 execute format('grant select,insert,update,delete on public.%I to service_role',t);
 end loop;
end $$;
create function private.kakao_weather_request_valid(p_forecast_day date,p_base_date text,p_base_time text) returns boolean language plpgsql stable security definer set search_path='' as $$
declare k timestamp:=clock_timestamp() at time zone 'Asia/Seoul'; b timestamp;released timestamp;expected timestamp;h integer;
begin
 if p_forecast_day is null or p_base_date is null or p_base_time is null or p_base_date !~ '^[0-9]{8}$' or p_base_time not in ('0200','0500','0800','1100','1400','1700','2000','2300') then return false;end if;
 b:=to_date(p_base_date,'YYYYMMDD')+make_time(left(p_base_time,2)::integer,0,0);
 if to_char(b,'YYYYMMDD')<>p_base_date then return false;end if;
 released:=k-interval '10 minutes';h:=extract(hour from released)::integer;
 expected:=case when h<2 then (released::date-1)+time '23:00' else released::date+make_time(2+((h-2)/3)*3,0,0) end;
 return b=expected and p_forecast_day in (k::date,k::date-1) and (p_forecast_day=k::date or k::time<'00:10'::time)
 and b<=k-interval '10 minutes' and b>=k-interval '30 hours' and b::date<=p_forecast_day;
exception when others then return false;
end $$;
create function private.kakao_service_weather_claim(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text) returns jsonb language plpgsql security definer set search_path='' as $$
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
create function private.kakao_service_weather_complete(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text,p_lease_token uuid,p_forecast jsonb) returns boolean language plpgsql security definer set search_path='' as $$
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
create function public.kakao_service_weather_claim(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_service_weather_claim(p_region_key,p_forecast_day,p_base_date,p_base_time)$$;
create function public.kakao_service_weather_complete(p_region_key text,p_forecast_day date,p_base_date text,p_base_time text,p_lease_token uuid,p_forecast jsonb) returns boolean language sql security invoker set search_path='' as $$select private.kakao_service_weather_complete(p_region_key,p_forecast_day,p_base_date,p_base_time,p_lease_token,p_forecast)$$;
revoke all on function private.kakao_weather_request_valid(date,text,text),private.kakao_service_weather_claim(text,date,text,text),public.kakao_service_weather_claim(text,date,text,text),private.kakao_service_weather_complete(text,date,text,text,uuid,jsonb),public.kakao_service_weather_complete(text,date,text,text,uuid,jsonb) from public,anon,authenticated;
grant execute on function private.kakao_weather_request_valid(date,text,text),private.kakao_service_weather_claim(text,date,text,text),public.kakao_service_weather_claim(text,date,text,text),private.kakao_service_weather_complete(text,date,text,text,uuid,jsonb),public.kakao_service_weather_complete(text,date,text,text,uuid,jsonb) to service_role;
commit;
