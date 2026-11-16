-- Local synthetic PostgreSQL only, net/cron recording stubs. No provider calls.
update public.kakao_multi_controls set enabled=true,monthly_message_budget=1000,monthly_function_budget=100,cost_verified_until=now()+interval '1 day',tick_endpoint='https://fake.supabase.co/functions/v1/hwarang-kakao/tick' where singleton;
update public.kakao_multi_function_budgets set monthly_shared_budget=100;
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled) select id,'web:1100000000',true from public.profiles;
create temporary table legacy_baseline as select (select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p) prefs;
do $$begin
 if exists(select 1 from net.http_request_queue) or exists(select 1 from public.kakao_multi_welcomes where status<>'legacy_excluded') then raise exception 'Retroactive welcome';end if;
end $$;
insert into public.profiles(login_id,display_name) values('welcome_new','Synthetic New'),('welcome_conflict','Synthetic Conflict'),('welcome_expire','Synthetic Expire');
insert into public.hwarang_app_access select id,'workspace',true from public.profiles where login_id like 'welcome_%';
insert into public.kakao_multi_connections(owner_id,account_id,encrypted_tokens,status,generation,talk_message_granted)
select id,'fake-'||login_id,'fake-cipher','connected',1,true from public.profiles where login_id like 'welcome_%';
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled)
select id,'web:1100000000',false from public.profiles where login_id like 'welcome_%';
do $$declare u uuid;w public.kakao_multi_welcomes;c jsonb;r jsonb;token uuid;oldhash text;parts text[]:=array['첫번째','두번째','세번째'];begin
 select id into u from public.profiles where login_id='welcome_new';
 if (select status from public.kakao_multi_welcomes where owner_id=u)<>'waiting_setup' or exists(select 1 from net.http_request_queue) then raise exception 'OFF sent welcome';end if;
 update public.kakao_multi_preferences set enabled=true where owner_id=u;
 select * into w from public.kakao_multi_welcomes where owner_id=u;
 if w.status<>'queued' or w.regular_not_before<>w.day+1 or (select count(*) from net.http_request_queue)<>1 then raise exception 'Ready did not enqueue exactly once';end if;
 if w.expires_at>w.ready_at+interval '10 minutes' or w.expires_at>((w.day+1)::timestamp at time zone 'Asia/Seoul') then raise exception 'Deadline overflow';end if;
 if private.kakao_welcome_regular_allowed(u,w.day) or not private.kakao_welcome_regular_allowed(u,w.day+1) then raise exception 'First regular day wrong';end if;
 update public.kakao_multi_preferences set enabled=true where owner_id=u;
 if (select count(*) from net.http_request_queue)<>1 then raise exception 'Repeated save duplicated';end if;
 c:=public.kakao_welcome_claim(w.ticket_hash);token:=(c->>'claim_token')::uuid;oldhash:=w.ticket_hash;
 if c is null or public.kakao_welcome_claim(w.ticket_hash) is not null then raise exception 'Ticket not one-use';end if;
 if public.kakao_welcome_reserve(w.id,token,array[repeat('😀',101)])->>'reserved'<>'false' then raise exception 'UTF16 overflow accepted';end if;
 if public.kakao_welcome_reserve(w.id,token,parts)->>'reserved'<>'true' then raise exception 'Reserve failed';end if;
 if jsonb_array_length(private.kakao_service_pending())<>0 then raise exception 'Normal worker can see welcome jobs';end if;
 if public.kakao_welcome_begin_part(w.id,token,2)->>'claimed'<>'false' then raise exception 'Out-of-order part';end if;
 if public.kakao_welcome_begin_part(w.id,token,1)->>'claimed'<>'true' then raise exception 'First part denied';end if;
 if public.kakao_welcome_continue(w.id,token) then raise exception 'Sending part continued';end if;
 if not public.kakao_welcome_complete_part(w.id,token,1,'accepted') then raise exception 'Complete denied';end if;
 if public.kakao_welcome_complete_part(w.id,token,1,'uncertain') then raise exception 'Accepted rewritten';end if;
 if not public.kakao_welcome_continue(w.id,token) or public.kakao_welcome_continue(w.id,token) then raise exception 'Continuation not exactly once';end if;
 if public.kakao_welcome_claim(oldhash) is not null then raise exception 'Old ticket reused';end if;
 select * into w from public.kakao_multi_welcomes where owner_id=u;
 c:=public.kakao_welcome_claim(w.ticket_hash);token:=(c->>'claim_token')::uuid;
 if c->'parts'<>to_jsonb(parts) or (c->>'next_part')::integer<>2 then raise exception 'Continuation manifest lost';end if;
 for i in 2..3 loop
 if public.kakao_welcome_begin_part(w.id,token,i)->>'claimed'<>'true' or not public.kakao_welcome_complete_part(w.id,token,i,'accepted') then raise exception 'Continuation failed';end if;
 end loop;
 if (select status from public.kakao_multi_welcomes where owner_id=u)<>'accepted' then raise exception 'Final not accepted';end if;
 if public.kakao_welcome_fail(w.id,token,'outcome_uncertain') then raise exception 'Accepted final downgraded';end if;
 update public.kakao_multi_connections set status='pending_confirmation',generation=2 where owner_id=u;
 update public.kakao_multi_connections set status='connected' where owner_id=u;
 if (select count(*) from net.http_request_queue)<>2 then raise exception 'Reconnect resent';end if;
 -- Existing normal day wins: never replace it or send an extra welcome.
 select id into u from public.profiles where login_id='welcome_conflict';
 insert into public.kakao_multi_batches(owner_id,day,generation,status) values(u,(clock_timestamp() at time zone 'Asia/Seoul')::date,1,'accepted');
 update public.kakao_multi_preferences set enabled=true where owner_id=u;
 if (select status from public.kakao_multi_welcomes where owner_id=u)<>'suppressed_existing_delivery' then raise exception 'Existing normal delivery ignored';end if;
 -- Abandoned sending is handled by existing expiry with no retry or tail send.
 select id into u from public.profiles where login_id='welcome_expire';update public.kakao_multi_preferences set enabled=true where owner_id=u;
 select * into w from public.kakao_multi_welcomes where owner_id=u;c:=public.kakao_welcome_claim(w.ticket_hash);token:=(c->>'claim_token')::uuid;
 perform public.kakao_welcome_reserve(w.id,token,array['first','tail']);perform public.kakao_welcome_begin_part(w.id,token,1);
 update public.kakao_multi_jobs set claimed_at=clock_timestamp()-interval '6 minutes' where batch_id=w.batch_id and part=1;
 perform private.kakao_service_expire();
 if private.kakao_welcome_status(u)->>'status'<>'uncertain' or public.kakao_welcome_continue(w.id,token) or public.kakao_welcome_validate(w.id,token) then raise exception 'Expired sending retry allowed';end if;
 if exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status in('sending','reserved')) then raise exception 'Expiry left retryable tail';end if;
 if (select count(*) from public.kakao_multi_runs where run_kind='test')<>0 then raise exception 'Welcome used test budget';end if;
 if has_function_privilege('authenticated','public.kakao_welcome_claim(text)','execute') or has_table_privilege('service_role','public.kakao_multi_welcomes','update') then raise exception 'Welcome ACL leak';end if;
end $$;
select 'PASS: legacy exclusion, OFF hold, first-ready one-use, day claim, UTF16 multipart/continuation, reconnect, normal conflict, expired sending no retry, normal budgets, ACL' as result;
-- The public status RPC must preserve the prior volatile expired-confirmation cleanup.
insert into auth.sessions(id,user_id) select gen_random_uuid(),id from public.profiles where login_id='qa_peer';
update public.kakao_multi_connections set status='pending_confirmation',confirmation_hash=repeat('c',64),confirmation_expires_at=clock_timestamp()-interval '1 second' where owner_id=(select id from public.profiles where login_id='qa_peer');
select set_config('request.jwt.claims',(select jsonb_build_object('sub',p.id,'session_id',s.id)::text from public.profiles p join auth.sessions s on s.user_id=p.id where p.login_id='qa_peer'),false);
set role authenticated;
select public.kakao_my_status();
reset role;
do $$begin if (select status from public.kakao_multi_connections where owner_id=(select id from public.profiles where login_id='qa_peer'))='pending_confirmation' then raise exception 'Status wrapper lost expiry cleanup';end if;end $$;
-- Next-day normal claim is not blocked by the abandoned welcome's former sending row.
-- Test-local clock injection, never a deployable operation.
create function private.qa_clock() returns timestamptz language sql stable as $$select current_setting('qa.clock')::timestamptz$$;
select set_config('qa.clock',(clock_timestamp()+interval '1 day')::text,false);
do $$declare f record;begin
 for f in select pg_get_functiondef(p.oid) definition from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='private' and p.proname like 'kakao_%' loop execute replace(f.definition,'clock_timestamp()','private.qa_clock()');end loop;
end $$;
update public.kakao_multi_controls set cost_verified_until=private.qa_clock()+interval '1 day';
do $$declare u uuid;d date:=(private.qa_clock() at time zone 'Asia/Seoul')::date;s jsonb;r jsonb;run uuid:=gen_random_uuid();job uuid;begin
 select id into u from public.profiles where login_id='welcome_expire';
 update public.kakao_multi_preferences set delivery_time=date_trunc('minute',private.qa_clock() at time zone 'Asia/Seoul')::time,days=array[0,1,2,3,4,5,6],send_empty=true where owner_id=u;
 s:=private.kakao_service_snapshot(u,d);
 r:=private.kakao_service_reserve(u,d,1,array['Next day regular'],private.kakao_service_snapshot_hash(s));
 if r->>'status'<>'reserved' then raise exception 'Next day reserve failed: %',r;end if;
 select id into job from public.kakao_multi_jobs where batch_id=(r->>'batch_id')::uuid;
 if not private.kakao_service_tick_enter(run) then raise exception 'Next day normal run denied';end if;
 update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;
 r:=private.kakao_service_claim(job,run);
 if r->>'claimed'<>'true' then raise exception 'Abandoned welcome blocked next day normal: %',r;end if;
end $$;
select 'PASS: volatile status cleanup and next-day normal claim after abandoned welcome' as next_day_result;
