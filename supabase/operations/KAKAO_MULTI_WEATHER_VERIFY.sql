-- Local synthetic fixture; no network or provider key. Everything rolls back.
begin;
insert into public.kakao_weather_regions(region_key,label,nx,ny,enabled,verified_at) values('test-grid','Synthetic Region',60,127,true,now()),('unverified','Unverified',60,127,true,null);
do $$
declare u uuid; sid uuid:=gen_random_uuid(); before_hash text; after_hash text; result jsonb; denied boolean:=false;
begin
 insert into public.profiles(login_id,display_name) values('weather_test','Synthetic Weather') returning id into u;
 insert into public.hwarang_app_access values(u,'workspace',true);
 insert into auth.sessions(id,user_id) values(sid,u);
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted) values(u,'connected',1,'synthetic-weather',repeat('cipher',10),true);
 insert into public.kakao_multi_preferences(owner_id) values(u);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',u,'role','authenticated','session_id',sid)::text,true);
 begin perform public.kakao_save_preferences(true,'08:00',array[1],true);exception when others then denied:=true;end;
 if not denied then raise exception 'Enabled without region';end if;
 denied:=false;
 begin perform public.kakao_save_weather_region('unverified');exception when others then denied:=true;end;
 if not denied then raise exception 'Unverified region accepted';end if;
 before_hash:=private.kakao_service_snapshot_hash(private.kakao_service_snapshot(u,current_date));
 result:=public.kakao_save_weather_region('test-grid');
 if result->>'weather_region_key'<>'test-grid' then raise exception 'Own status missing region';end if;
 after_hash:=private.kakao_service_snapshot_hash(private.kakao_service_snapshot(u,current_date));
 if before_hash=after_hash then raise exception 'Region omitted from snapshot hash';end if;
 update public.kakao_weather_regions set nx=61 where region_key='test-grid';
 if after_hash=private.kakao_service_snapshot_hash(private.kakao_service_snapshot(u,current_date)) then raise exception 'Catalog change omitted from hash';end if;
 perform public.kakao_save_preferences(true,'08:00',array[1],true);
 perform public.kakao_save_weather_region(null);
 if (select enabled from public.kakao_multi_preferences where owner_id=u) then raise exception 'Null selection did not disable';end if;
 result:=public.kakao_weather_regions();
 if jsonb_array_length(result)<>1 or result->0->>'display_name'<>'Synthetic Region' or (result->0)?'nx' then raise exception 'Catalog projection invalid';end if;
end $$;
set local role authenticated;
select public.kakao_weather_regions() as verified_catalog;
do $$begin
 begin perform 1 from public.kakao_weather_regions;raise exception 'Direct table leak';exception when insufficient_privilege then null;end;
end $$;
reset role;
set local role anon;
do $$begin
 begin perform public.kakao_weather_regions();raise exception 'Anon RPC leak';exception when insufficient_privilege then null;end;
end $$;
reset role;
select 'weather selection, validation, hash, disable and actual role ACL passed' as result;
rollback;
