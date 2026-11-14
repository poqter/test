import {PGlite} from './studio_db/node_modules/@electric-sql/pglite/dist/index.js';
import fs from 'node:fs';
const db=new PGlite();
await db.exec(`create role anon;create role authenticated;create role service_role bypassrls;
create schema auth;create schema extensions;
create table auth.users(id uuid primary key,email text,raw_user_meta_data jsonb default '{}',created_at timestamptz default now());
create function auth.uid() returns uuid language sql as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
create function extensions.digest(text,text) returns bytea language sql as $$select decode(md5($1),'hex')$$;
create function extensions.gen_random_bytes(integer) returns bytea language sql as $$select decode(repeat('00',$1),'hex')$$;
`);
const root=new URL('../supabase/migrations',import.meta.url).pathname;
for(const n of [1,3,4,5,6,7,8,9,10,11,12,13,14,15,17,18,23,24,25,26]){
 const name=fs.readdirSync(root).find(x=>x.startsWith(String(n).padStart(2,'0')+'_'));
 let sql=fs.readFileSync(root+'/'+name,'utf8').replace(/create extension if not exists pgcrypto with schema extensions;/gi,'');
 try{await db.exec(sql);console.log('Applied',name)}catch(e){console.log('FAILED',name,e.message);process.exit(1)}
}
for(const n of [25,26]){const name=fs.readdirSync(root).find(x=>x.startsWith(String(n)+'_'));await db.exec(fs.readFileSync(root+'/'+name,'utf8'));}
console.log('MIGRATION PASS; 25/26 repeat-safe');
const owner='00000000-0000-0000-0000-000000000001', manager='00000000-0000-0000-0000-000000000002', outsider='00000000-0000-0000-0000-000000000003';
await db.exec(`alter table auth.users disable trigger user;
insert into auth.users(id,email) values('${owner}','owner@test.invalid'),('${manager}','manager@test.invalid'),('${outsider}','other@test.invalid');
insert into public.profiles(id,login_id,display_name,role,is_active) values('${owner}','testowner','교육생','user',true),('${manager}','testmanager','관리자','super_admin',true),('${outsider}','testother','외부직원','user',true);
insert into public.hwarang_app_access(user_id,app_code,is_enabled) values('${owner}','academy',true),('${manager}','academy',true),('${outsider}','academy',true) on conflict(user_id,app_code) do update set is_enabled=true;
update public.hwarang_ai_runtime_config set service_enabled=true,text_enabled=true,voice_enabled=true,assessment_enabled=true;
`);


const assert=(await import('node:assert/strict')).default;
await db.exec(fs.readFileSync(root+'/20261030015818_academy_onboarding_v1.sql','utf8'));
await db.exec(fs.readFileSync(root+'/20261114030828_academy_fp_foundation_v2.sql','utf8'));
const reviewer='00000000-0000-0000-0000-000000000004';
await db.exec(`insert into auth.users(id,email) values('${reviewer}','review@test.invalid');insert into public.profiles(id,login_id,display_name,role,is_active) values('${reviewer}','review','검토자','super_admin',true);insert into public.hwarang_app_access(user_id,app_code,is_enabled) values('${reviewer}','academy',true) on conflict(user_id,app_code) do update set is_enabled=true;`);
// Match the verified production service-role helper grant.
await db.exec('grant execute on function private.can_user_view(uuid,uuid) to service_role;set role service_role');
const call=async(actor,lesson,version,answers,submit=true)=>(await db.query('select public.hwarang_learning_interactive_save($1,$2,1,$3,$4,$5,$6) r',[actor,'fp-foundation-v2',lesson,version,answers,submit])).rows[0].r;
await assert.rejects(()=>call(owner,'l01',0,{pick:1,transfer:2}),/COURSE_UNDER_REVIEW/);
assert.equal((await call(manager,'l01',0,{pick:0,transfer:2})).passed,false);
assert.equal((await call(manager,'l01',0,{pick:1,transfer:2},false)).status,'draft');
await assert.rejects(()=>call(manager,'l01',0,{pick:1,transfer:2}),/WORK_CHANGED/);
assert.equal((await call(manager,'l01',1,{pick:1,transfer:2})).status,'submitted');
await assert.rejects(()=>call(manager,'l01',2,{pick:1,transfer:2}),/SUBMITTED_WORK_LOCKED/);
await assert.rejects(()=>call(manager,'p1',0,{},true),/OPTIONAL_DRAFT_ONLY/);
assert.equal((await call(manager,'p1',0,{_state:[true,false,false]},false)).status,'draft');
await call(manager,'m1',0,{q0:1,q1:2,q2:0});
await assert.rejects(()=>db.query("select public.hwarang_learning_work_review($1,$1,'fp-foundation-v2',1,'m1',1,true,$2)",[manager,{good:'좋음',improve:'보완',next:'다음'}]),/LEARNING_ACCESS_DENIED/);
await db.query("select public.hwarang_learning_work_review($1,$2,'fp-foundation-v2',1,'m1',1,false,$3)",[reviewer,manager,{good:'좋음',improve:'보완',next:'다음'}]);
await call(manager,'m1',2,{q0:1,q1:2,q2:0});
await db.query("select public.hwarang_learning_work_review($1,$2,'fp-foundation-v2',1,'m1',3,true,$3)",[reviewer,manager,{good:'좋음',improve:'보완',next:'다음'}]);
assert.equal((await db.query("select count(*)::int n from public.hwarang_learning_work_events where lesson_id='m1'")).rows[0].n,4);
assert.equal((await db.query("select count(*)::int n from public.hwarang_learning_content where id='newhire-30-v1'")).rows[0].n,1);
await db.exec('reset role;set role authenticated');
await assert.rejects(()=>call(manager,'l03',0,{}),/permission denied/);
await assert.rejects(()=>db.query('select * from public.hwarang_learning_work_events'),/permission denied/);
await db.close();console.log('PASS foundation DB: gate, grading, drafts, version conflicts, locks, resubmission, real review, audit, isolation, legacy preservation');
