create temporary table before_state as select (select count(*) from public.kakao_multi_batches) batches,(select count(*) from public.kakao_multi_jobs) jobs,(select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) slots,(select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p) prefs;
insert into public.kakao_multi_test_requests(owner_id,request_slot,cached_weather_only,ticket_hash,expires_at) select id,2,true,repeat('e',64),now()+interval '3 minutes' from public.profiles where login_id='qa_staff';
do $$begin if public.kakao_test_claim(repeat('e',64)) is not null then raise exception 'Missing cache allowed';end if;end $$;
insert into public.kakao_weather_cache(nx,ny,forecast_day,base_date,base_time,forecast,expires_at) values(60,127,(clock_timestamp() at time zone 'Asia/Seoul')::date,to_char(clock_timestamp() at time zone 'Asia/Seoul','YYYYMMDD'),'0200',jsonb_build_object('status','ok','day',(clock_timestamp() at time zone 'Asia/Seoul')::date),now()+interval '10 minutes');
do $$declare r jsonb;begin
 r:=public.kakao_test_claim(repeat('e',64));
 if r is null or r->>'cached_weather_only'<>'true' or r->'cached_weather'->>'status'<>'ok' then raise exception 'Fresh cache not available';end if;
 if exists(select 1 from public.kakao_weather_usage) then raise exception 'Extra weather consumed';end if;
 if public.kakao_test_claim(repeat('e',64)) is not null then raise exception 'Second slot replayed';end if;
 begin insert into public.kakao_multi_test_requests(owner_id,request_slot,cached_weather_only,ticket_hash,expires_at) select id,3,true,repeat('f',64),now()+interval '3 minutes' from public.profiles where login_id='qa_staff';raise exception 'Third slot allowed';exception when check_violation then null;end;
 if exists(select 1 from before_state b where b.batches<>(select count(*) from public.kakao_multi_batches) or b.jobs<>(select count(*) from public.kakao_multi_jobs) or b.slots is distinct from (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) or b.prefs is distinct from (select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p)) then raise exception 'Normal state changed';end if;
end $$;
select 'PASS: second approved slot, cache required, no weather budget consumed, no replay, third slot blocked, normal state unchanged' as result;
