import {PGlite} from './studio_db/node_modules/@electric-sql/pglite/dist/index.js';
import fs from 'node:fs';import assert from 'node:assert/strict';
const db=new PGlite();
await db.exec('create schema private;create role anon;create role authenticated;create role service_role;');
await db.exec(fs.readFileSync(new URL('./kakao_branch_schema.sql',import.meta.url),'utf8'));
await db.exec(`
create function private.kakao_service_owner_active(uuid) returns boolean language sql as $$select exists(select 1 from public.profiles where id=$1 and is_active)$$;
create function private.kakao_welcome_regular_allowed(uuid,date) returns boolean language sql as $$select true$$;
create function private.kakao_service_snapshot_hash(jsonb) returns text language sql as $$select md5($1::text)$$;
create function private.kakao_function_budget_ok(text,boolean) returns boolean language sql as $$select true$$;
create function private.kakao_service_legacy_conflict(text) returns boolean language sql as $$select false$$;
alter table public.kakao_multi_batches alter id set default gen_random_uuid(),alter status set default 'reserved',alter created_at set default now();
alter table public.kakao_multi_jobs alter id set default gen_random_uuid(),alter status set default 'reserved';
`);
await db.exec(fs.readFileSync(new URL('../supabase/operations/KAKAO_BRANCH_BRIEFING_PATCH.sql',import.meta.url),'utf8'));
await db.exec(fs.readFileSync(new URL('../supabase/operations/KAKAO_BRANCH_LEAVE_EXCLUSIONS_PATCH.sql',import.meta.url),'utf8'));
await db.exec("create table sales_team_assignments(member uuid,leader uuid);create table sales_deputy_assignments(member uuid,leader uuid);create function private.kakao_require_user() returns uuid language sql as $select null::uuid$;");
await db.exec(fs.readFileSync(new URL('../supabase/operations/KAKAO_BRANCH_CONNECTED_MEMBERS_PATCH.sql',import.meta.url),'utf8'));
const id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const day=(await db.query("select (now() at time zone 'Asia/Seoul')::date::text as day")).rows[0].day;
await db.query("insert into organization_units(id,name,is_active) values($1,'테스트지점',true)",[id(99)]);
for(const [n,position,unit,active] of [[1,'branch_manager',99,true],[2,'fp',99,true],[3,'fp',99,true],[4,'fp',99,true],[5,'fp',99,true],[6,'fp',98,true],[7,'fp',99,false],[8,'branch_manager',99,true],[9,'division_head',99,true]])await db.query("insert into profiles(id,display_name,position_code,organization_unit_id,is_active,role) values($1,$2,$3,$4,$5,'user')",[id(n),'직원'+n,position,id(unit),active]);
async function event(owner,kind='AP',status='예정',common=false,companion=null,deleted=false){
 await db.query("insert into sales_events(id,owner,unit,day,kind,status,common,title,companion,deleted_at) values(gen_random_uuid(),$1,$2,$3,$4,$5,$6,'합성일정',$7,case when $8 then now() end)",[id(owner),id(owner===6?98:99),day,kind,status,common,companion?id(companion):null,deleted]);
}
await event(1);await event(2);await event(2,'AP','취소');await event(2,'AP','연기');await event(2,'AP','예정',false,null,true);await event(2,'AP','예정',true);
await event(3,'휴무');await event(6);await event(7);await event(8);
await db.query('insert into sales_empty_days values($1,$2)',[id(4),day]);
const snapshot=async(owner=1)=>(await db.query('select private.kakao_service_snapshot($1,$2) s',[id(owner),day])).rows[0].s;
let s=await snapshot();assert.deepEqual(s.branch.members.map(m=>[m.name,m.count,m.state]),[['직원2',1,'scheduled'],['직원3',0,'leave'],['직원4',0,'empty'],['직원5',0,'missing'],['직원9',0,'excluded']]);
assert.equal((await snapshot(2)).branch,null);
await event(2,'휴무');await event(2,'휴무');
s=await snapshot();assert.equal(s.branch.members.find(m=>m.name==='직원2').count,1);assert.equal(s.branch.members.find(m=>m.name==='직원2').on_leave,true);
assert.equal(s.branch.members.filter(m=>m.on_leave).length,2,'leave counted by person, including scheduled people');
await db.query("insert into profiles(id,display_name,position_code,organization_unit_id,is_active) values($1,'합성 테스트','fp',$2,true)",[id(10),id(99)]);
await db.query("insert into private.kakao_briefing_member_exclusions(member_id,reason) values($1,'synthetic fixture')",[id(10)]);
assert.ok(!(await snapshot()).branch.members.some(m=>m.id===id(10)));
await event(10);assert.ok(!(await snapshot()).branch.members.some(m=>m.id===id(10)),'excluded with schedules too');
await db.query("update profiles set display_name='이름변경' where id=$1",[id(10)]);
assert.ok(!(await snapshot()).branch.members.some(m=>m.id===id(10)),'stable identity exclusion');

await event(2,'AP','예정',false,5);s=await snapshot();assert.equal(s.branch.members.find(m=>m.name==='직원5').count,1);
await db.exec("insert into kakao_multi_controls(singleton,enabled,monthly_message_budget,monthly_function_budget,cost_verified_until) values(true,true,100,100,now()+interval '1 day')");
await db.query("insert into kakao_multi_connections(owner_id,status,generation,talk_message_granted,account_id,encrypted_tokens) values($1,'connected',1,true,'synthetic','synthetic')",[id(1)]);
await db.query("insert into kakao_multi_preferences(owner_id,delivery_time,days,enabled,send_empty,admin_paused) values($1,(now() at time zone 'Asia/Seoul'-interval '1 minute')::time,array[0,1,2,3,4,5,6],true,false,false)",[id(1)]);
await db.query('delete from sales_events where owner=$1 or common',[id(1)]);
s=await snapshot();assert.equal(s.events.length,0);
const hash=(await db.query('select private.kakao_service_snapshot_hash($1) h',[JSON.stringify(s)])).rows[0].h;
const reserve=async()=>(await db.query("select public.kakao_service_reserve_branch($1,$2,1,array['지점','개인날씨'],$3,1)",[id(1),day,hash])).rows[0].kakao_service_reserve_branch;
assert.equal((await reserve()).status,'reserved');assert.equal((await reserve()).status,'already_reserved');
const jobs=(await db.query('select id from kakao_multi_jobs order by part')).rows;
async function claim(job){
 const run=(await db.query("insert into kakao_multi_runs(id,entered_at,run_kind) values(gen_random_uuid(),now(),'normal') returning id")).rows[0].id;
 return (await db.query('select private.kakao_service_claim($1,$2) r',[job,run])).rows[0].r;
}
assert.equal((await claim(jobs[1].id)).reason,'previous_incomplete');
assert.equal((await claim(jobs[0].id)).message_kind,'branch');
await db.query("update kakao_multi_jobs set status='accepted' where id=$1",[jobs[0].id]);
assert.equal((await claim(jobs[1].id)).message_kind,'personal');
const grants=(await db.query("select has_function_privilege('anon','public.kakao_service_reserve_branch(uuid,date,bigint,text[],text,integer)','execute') a,has_function_privilege('authenticated','public.kakao_service_reserve_branch(uuid,date,bigint,text[],text,integer)','execute') b")).rows[0];
assert.equal(grants.a,false);assert.equal(grants.b,false);
const welcomeSource=fs.readFileSync(new URL('../supabase/operations/KAKAO_MULTI_WELCOME_PATCH.sql',import.meta.url),'utf8');
await db.exec(welcomeSource.slice(welcomeSource.indexOf('create function private.kakao_welcome_reserve('),welcomeSource.indexOf('create function private.kakao_welcome_begin_part(')));
await db.exec("create function private.kakao_welcome_validate(uuid,uuid) returns boolean language sql as $$select true$$");
const batch=(await db.query("insert into kakao_multi_batches(owner_id,day) values($1,$2) returning id",[id(1),day])).rows[0].id;
await db.query("insert into kakao_multi_welcomes(id,owner_id,batch_id) values($1,$2,$3)",[id(40),id(1),batch]);
const welcome=(await db.query("select public.kakao_welcome_reserve_branch($1,$2,array['지점','본인'],1) r",[id(40),id(41)])).rows[0].r;
assert.equal(welcome.reserved,true);assert.equal((await db.query('select branch_parts from kakao_multi_batches where id=$1',[batch])).rows[0].branch_parts,1);

for(const [n,pos] of [[20,'team_leader'],[21,'deputy_branch_manager'],[22,'team_leader'],[23,'fp']]){
 await db.query("insert into profiles(id,display_name,position_code,organization_unit_id,is_active,role) values($1,$2,$3,$4,true,'super_admin')",[id(n),'직원'+n,pos,id(99)]);
}
await db.query('insert into sales_team_assignments values($1,$2),($3,$2),($4,$2),($5,$2),($6,$2)',[id(2),id(20),id(3),id(6),id(7),id(10)]);
await db.query('insert into sales_deputy_assignments values($1,$2),($3,$2),($4,$2)',[id(20),id(21),id(2),id(23)]);
assert.deepEqual((await snapshot(20)).branch.members.map(m=>m.id).sort(),[id(2),id(3)].sort(),'team FP only; exclude inactive, cross-unit, test');
assert.deepEqual((await snapshot(21)).branch.members.map(m=>m.id).sort(),[id(2),id(3),id(20),id(23)].sort(),'deputy direct and indirect, deduplicated');
assert.equal((await snapshot(22)).branch,null,'no fallback to whole branch');
await db.query("insert into kakao_multi_preferences(owner_id,member_briefing_enabled) values($1,false)",[id(21)]);
assert.equal((await snapshot(21)).branch,null,'independent opt-out');
assert.ok((await db.query('select private.kakao_member_summary($1,$2) s',[id(21),day])).rows[0].s.members.length>0,'preview still shows eligible scope');
await db.query('update profiles set is_active=false where id=$1',[id(20)]);
await db.query('update kakao_multi_preferences set member_briefing_enabled=true where owner_id=$1',[id(21)]);
assert.deepEqual((await snapshot(21)).branch.members.map(m=>m.id).sort(),[id(2),id(23)].sort(),'inactive intermediate team leader removes inherited FP');
await db.query("update profiles set position_code='fp' where id=$1",[id(21)]);
assert.equal((await snapshot(21)).branch,null,'super admin does not override actual role');
const acl=(await db.query("select has_function_privilege('anon','public.kakao_member_briefing_status()','execute') a,has_function_privilege('authenticated','private.kakao_member_summary(uuid,date)','execute') b,has_function_privilege('authenticated','public.kakao_member_briefing_status()','execute') c")).rows[0];
assert.equal(acl.a,false);assert.equal(acl.b,false);assert.equal(acl.c,true);
await db.close();console.log('PASS branch scope, states, empty personal day, ordered claims, duplicate prevention, RPC grants');
