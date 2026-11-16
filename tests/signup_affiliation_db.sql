-- Run against the isolated fixture plus migration. Synthetic accounts only.
create trigger on_auth_user_created after insert on auth.users for each row execute function private.handle_new_hwarang_user();
insert into organization_units values
('00000000-0000-0000-0000-000000000001','VISION_HQ','HQ',null,'head_unit',true,1),
('00000000-0000-0000-0000-000000000002','TEST_BRANCH','Branch','00000000-0000-0000-0000-000000000001','branch',true,1),
('00000000-0000-0000-0000-000000000003','OTHER_BRANCH','Other',null,'branch',true,2),
('00000000-0000-0000-0000-000000000004','PLATFORM_OPERATIONS','Ops',null,'branch',true,3);
insert into hwarang_join_codes values('00000000-0000-0000-0000-000000000010','QA',null,true,true,now()-interval '1 day',null,null,0),('00000000-0000-0000-0000-000000000011','BRANCH','00000000-0000-0000-0000-000000000002',true,true,now()-interval '1 day',null,null,0);
insert into profiles(id,role,is_active,organization_unit_id,position_code,display_name) values
('00000000-0000-0000-0000-000000000021','user',true,'00000000-0000-0000-0000-000000000002','team_leader','Leader'),
('00000000-0000-0000-0000-000000000022','user',true,'00000000-0000-0000-0000-000000000002','deputy_branch_manager','Deputy'),
('00000000-0000-0000-0000-000000000023','user',true,'00000000-0000-0000-0000-000000000003','team_leader','Other');
do $$declare pos text;i int:=30;begin
 foreach pos in array array['fp','partner','team_leader','deputy_branch_manager','branch_manager','division_head'] loop
 i:=i+1;insert into auth.users values(('00000000-0000-0000-0000-'||lpad(i::text,12,'0'))::uuid,'qa'||i||'@example.invalid',jsonb_build_object('signup_mode','hwarang_self_signup','login_id','qa'||i,'display_name','QA','join_code','QA','organization_code',case when pos='division_head' then 'VISION_HQ' else 'TEST_BRANCH' end,'position_code',pos));
 end loop;
 if (select count(*) from profiles where login_id like 'qa%' and role='user')<>6 then raise exception 'SIX_POSITIONS_FAILED';end if;
 if exists(select 1 from auth.users where raw_user_meta_data?'join_code') then raise exception 'JOINCODE_RETAINED';end if;
 if exists(select 1 from signup_affiliation_options('QA') where organization_code='PLATFORM_OPERATIONS') then raise exception 'PLATFORM_EXPOSED';end if;
 if exists(select 1 from signup_affiliation_options('BAD')) then raise exception 'BAD_CODE_EXPOSED';end if;
 begin
 insert into auth.users values('00000000-0000-0000-0000-000000000099','bad@example.invalid',jsonb_build_object('signup_mode','hwarang_self_signup','login_id','bad99','display_name','bad','join_code','QA','organization_code','TEST_BRANCH','position_code','platform_administrator'));
 raise exception 'FORBIDDEN_ACCEPTED'; exception when raise_exception then if sqlerrm='FORBIDDEN_ACCEPTED' then raise;end if;end;
 begin
 insert into auth.users values('00000000-0000-0000-0000-000000000098','bad@example.invalid',jsonb_build_object('signup_mode','hwarang_self_signup','login_id','bad98','display_name','bad','join_code','BRANCH','organization_code','VISION_HQ','position_code','division_head'));
 raise exception 'BRANCH_ESCALATED'; exception when raise_exception then if sqlerrm='BRANCH_ESCALATED' then raise;end if;end;
 if (select used_count from hwarang_join_codes where code_hash='QA')<>6 then raise exception 'FAILED_SIGNUP_NOT_ATOMIC';end if;
end $$;
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000031',false);
select public.set_reporting_managers('00000000-0000-0000-0000-000000000021','00000000-0000-0000-0000-000000000022');
do $$begin
 if (public.get_reporting_managers()->>'team_leader')<>'00000000-0000-0000-0000-000000000021' then raise exception 'SAVE_FAILED';end if;
 begin perform public.set_reporting_managers('00000000-0000-0000-0000-000000000023',null);raise exception 'CROSS_ORG_ACCEPTED';exception when raise_exception then if sqlerrm='CROSS_ORG_ACCEPTED' then raise;end if;end;
 begin perform public.signup_affiliation_options('QA');raise exception 'AUTH_SIGNUP_OPTIONS_ALLOWED';exception when insufficient_privilege then null;end;
end $$;
select public.set_reporting_managers(null,null);
reset role;
do $$begin
 if exists(select 1 from sales_team_assignments where member='00000000-0000-0000-0000-000000000031') then raise exception 'CLEAR_FAILED';end if;
 if has_function_privilege('anon','public.set_reporting_managers(uuid,uuid)','execute') then raise exception 'ANON_WRITE';end if;
end $$;
insert into sales_team_assignments values('00000000-0000-0000-0000-000000000021','00000000-0000-0000-0000-000000000033');
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000033',false);
do $$begin
 if exists(select 1 from jsonb_array_elements(public.get_reporting_managers()->'candidates') c where c->>'id' in ('00000000-0000-0000-0000-000000000033','00000000-0000-0000-0000-000000000021')) then raise exception 'CYCLE_CANDIDATE';end if;
 begin perform public.set_reporting_managers('00000000-0000-0000-0000-000000000021',null);raise exception 'CYCLE_ACCEPTED';exception when raise_exception then if sqlerrm='CYCLE_ACCEPTED' then raise;end if;end;
end $$;
reset role;
select 'signup/self-reporting DB regression PASS' as result;
