-- LOCAL MOCK DB ONLY: net.http_post records requests without sending. Rollback fixtures.
begin;
create temporary table kakao_chain_results(name text);
do $$declare u uuid; d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date; bid uuid; parent text:=repeat('e',64); result boolean; before_count int;begin
 select id into u from public.profiles where login_id='qa_staff';
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted) values(u,'connected',1,'900000000078',repeat('dummy',10),true);
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time) values(u,true,to_char(clock_timestamp() at time zone 'Asia/Seoul','HH24:MI')::time);
 update public.kakao_multi_controls set enabled=true,monthly_message_budget=100,monthly_function_budget=100,cost_verified_until=clock_timestamp()+interval '1 hour',tick_endpoint='https://example.supabase.co/functions/v1/hwarang-kakao/tick';
 insert into public.kakao_multi_batches(owner_id,day,generation,scope_hash,delivery_deadline) values(u,d,1,private.kakao_service_snapshot_hash(private.kakao_service_snapshot(u,d)),clock_timestamp()+interval '5 minutes') returning id into bid;
 insert into public.kakao_multi_jobs(batch_id,owner_id,generation,part,body) values(bid,u,1,1,'synthetic continuation');
 insert into public.kakao_multi_tick_tickets(ticket_hash,expires_at,used_at) values(parent,clock_timestamp()+interval '2 minutes',clock_timestamp());
 select count(*) into before_count from net.http_request_queue;
 if not public.kakao_service_continue(parent,true) then raise exception 'Expected continuation'; end if;
 if public.kakao_service_continue(parent,true) then raise exception 'Repeated parent created second child'; end if;
 if (select count(*) from net.http_request_queue)<>before_count+1 then raise exception 'Wrong child request count'; end if;
 if exists(select 1 from net.http_request_queue where headers ? 'Authorization' or (body-'ticket')<>'{}'::jsonb) then raise exception 'Persistent secret/body included'; end if;
 insert into kakao_chain_results values('Progress creates exactly one child request; parent replay creates none');
 insert into kakao_chain_results values('Continuation request contains only ephemeral ticket, no auth header or message');
end$$;
select jsonb_agg(name) as passed from kakao_chain_results;
rollback;
