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

const migration=fs.readFileSync(root+'/20261111075456_admin_asset_request_receipts.sql','utf8');
await db.exec(migration);await db.exec(migration);
const assert=(await import('node:assert/strict')).default;
const {randomUUID}=await import('node:crypto');
async function apply(id,asset='training_credit',targets=[owner,outsider],operation='grant',amount=100,actor=manager){
 return (await db.query('select public.admin_apply_hwarang_asset_request($1,$2,$3,$4,$5,$6,$7,$8) as result',
 [actor,id,asset,targets,operation,amount,'promotion_reward','synthetic test'])).rows[0].result;
}
async function count(table){return (await db.query('select count(*)::int as n from public.'+table)).rows[0].n}
await db.exec('set role service_role');
const request=randomUUID();
const result=await apply(request);
assert.equal(result.success_count,2);assert.equal(result.request_id,request);
const credits=await count('hwarang_ai_credit_ledger'),audits=await count('hwarang_admin_audit_log');
for(let i=0;i<3;i++)assert.deepEqual(await apply(request),result);
assert.equal(await count('hwarang_ai_credit_ledger'),credits);
assert.equal(await count('hwarang_admin_audit_log'),audits);
assert.deepEqual((await db.query('select public.admin_get_hwarang_asset_request($1,$2) as result',[manager,request])).rows[0].result,result);
assert.equal((await db.query('select public.admin_get_hwarang_asset_request($1,$2) as result',[manager,randomUUID()])).rows[0].result,null);
await assert.rejects(()=>apply(request,'training_credit',[owner], 'grant',500),/ASSET_REQUEST_CONFLICT/);
await assert.rejects(()=>apply(randomUUID(),'training_credit',[owner], 'grant',100,owner),/SUPER_ADMIN_REQUIRED/);
await assert.rejects(()=>apply(randomUUID(),'training_credit',[], 'grant',100),/TARGET_USERS_REQUIRED/);
await assert.rejects(()=>apply(randomUUID(),'training_credit',[owner], 'grant',null),/INVALID_ASSET_REQUEST/);
const partial=await apply(randomUUID(),'training_credit',[owner,randomUUID()]);
assert.equal(partial.success_count,1);assert.equal(partial.failed_count,1);
const voiceId=randomUUID(),voice=await apply(voiceId,'voice',[owner], 'grant',10);
assert.equal(voice.success_count,1);
const voiceCount=await count('hwarang_voice_ledger');
assert.deepEqual(await apply(voiceId,'voice',[owner], 'grant',10),voice);
assert.equal(await count('hwarang_voice_ledger'),voiceCount);
await db.query('update public.hwarang_voice_accounts set reserved_seconds=60 where user_id=$1',[owner]);
const denied=await apply(randomUUID(),'voice',[owner],'revoke',1);
assert.equal(denied.failed_count,1);assert.equal(await count('hwarang_voice_ledger'),voiceCount);
await db.exec('reset role;set role authenticated');
await assert.rejects(()=>apply(randomUUID()),/permission denied/);
await assert.rejects(()=>db.query('select * from private.hwarang_admin_asset_requests'),/permission denied/);
await db.exec('reset role;set role anon');
await assert.rejects(()=>apply(randomUUID()),/permission denied/);
await db.exec('reset role');
await db.query('update public.profiles set is_active=false where id=$1',[manager]);
await db.exec('set role service_role');
await assert.rejects(()=>apply(request),/SUPER_ADMIN_REQUIRED/);
console.log('PASS: actual ledger functions, repeat-safe receipts, response recovery, conflicting replay, Credit/Voice, partial failure, active reservations, role isolation and migration replay');
await db.close();
