import {fileURLToPath} from 'node:url';import path from 'node:path';
process.chdir(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'));
import {bank} from './fixture.mjs';
import {PGlite} from '@electric-sql/pglite';
import fs from 'node:fs';import assert from 'node:assert/strict';
const db=new PGlite();let checks=0;
const stable=v=>JSON.stringify(v,(k,x)=>k==='server_now'?undefined:x);
const ok=(v)=>{assert.ok(v);checks++};
const sql=fs.readFileSync('tests/exams/v1_schema.sql','utf8');
await db.exec(`create role anon;create role authenticated;create role service_role bypassrls;create schema private;
create table public.organization_units(id uuid primary key,name text,unit_type text,parent_id uuid);
create table public.profiles(id uuid primary key,display_name text,role text,position_code text,organization_unit_id uuid,is_active boolean default true);
create table public.hwarang_app_access(user_id uuid,app_code text,is_enabled boolean);
create function public.get_hwarang_effective_permissions(uuid) returns table(permission_code text) language sql as $$select 'academy.assessment'::text$$;
create function private.is_org_descendant(a uuid,b uuid) returns boolean language sql as $$with recursive t as(select id from public.organization_units where id=a union all select o.id from public.organization_units o join t on o.parent_id=t.id)select exists(select 1 from t where id=b)$$;`);
const platform=fs.readFileSync('supabase/migrations/06_Platform_Update.sql','utf8');
await db.exec(platform.slice(platform.indexOf('create or replace function private.can_user_view('),platform.indexOf('revoke all on function private.can_user_view')));
await db.exec(sql);await db.exec(sql);await db.exec(fs.readFileSync('supabase/operations/UPGRADE_CBT_UX_V2.sql','utf8'));await db.exec(fs.readFileSync('supabase/operations/UPGRADE_CBT_UX_V2.sql','utf8')); // repeatable schema
for(const b of bank) await db.query('insert into hwarang_exam_bank(id,title,family,revision,data) values($1,$2,$3,$4,$5)',[b.id,b.title,b.family,b.revision,b.data]);
const uid=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const orgs=[['root','총괄',null],['head_unit','본부',100],['branch','지점',101],['team','1팀',102],['team','2팀',102]];
for(let i=0;i<orgs.length;i++)await db.query('insert into organization_units values($1,$2,$3,$4)',[uid(100+i),orgs[i][1],orgs[i][0],orgs[i][2]===null?null:uid(orgs[i][2])]);
const people=[['fp',103],['fp',104],['team_leader',103],['deputy_branch_manager',102],['branch_manager',102],['division_head',101],['chief_representative',100],['fp',104]];
for(let i=0;i<people.length;i++){await db.query('insert into profiles values($1,$2,$3,$4,$5,true)',[uid(i+1),'사용자'+(i+1),i===7?'super_admin':'user',people[i][0],uid(people[i][1])]);await db.query("insert into hwarang_app_access values($1,'academy',true)",[uid(i+1)]);}
const call=async(actor,action,p={})=>(await db.query('select public.hwarang_exam($1,$2,$3::jsonb) result',[uid(actor),action,JSON.stringify(p)])).rows[0].result;
const denied=async(fn,part)=>{await assert.rejects(fn,new RegExp(part));checks++};
ok((await call(1,'list')).length===0);ok((await call(3,'roster')).length===2);ok((await call(3,'team')).length===0);
ok((await call(1,'catalog')).length===36);
let serial=1000;
for(const b of bank){for(const track of ['main','third','combined']){
 let a=await call(1,'start',{id:uid(serial++),exam_id:b.id,track,mode:'exam'});
 ok(a.questions.every(q=>!('answer'in q)&&!('explanation'in q)));ok(Number(a.remaining_seconds)<=3000&&Number(a.remaining_seconds)>2990);
 const answers=Object.fromEntries(b.data.questions.filter(q=>a.questions.some(x=>x.number===q.number)).map(q=>[q.number,q.answer]));
 a=await call(1,'save',{id:a.id,revision:a.revision,answers,flags:[],cursor:0});
 a=await call(1,'submit',{id:a.id,revision:a.revision});ok(a.result.sections.every(s=>s.score===100&&s.passed));
 const again=await call(1,'submit',{id:a.id,revision:0});ok(stable(a)===stable(again));
}}
let a=await call(1,'start',{id:uid(serial++),exam_id:bank[18].id,track:'combined',mode:'exam'});
ok((await call(1,'start',{id:uid(serial++),exam_id:bank[0].id,track:'main',mode:'exam'})).id===a.id);
await denied(()=>call(2,'get',{id:a.id}),'EXAM_ACCESS_DENIED');
for(const manager of [3,4,5,6,7,8])ok((await call(manager,'get',{id:a.id})).id===a.id);
await denied(()=>call(3,'save',{id:a.id,revision:0,answers:{},flags:[],cursor:0}),'EXAM_ACCESS_DENIED');
await denied(()=>call(1,'team'),'EXAM_ACCESS_DENIED');
await denied(()=>call(1,'save',{id:a.id,revision:0,answers:{1:9},flags:[],cursor:0}),'INVALID_ANSWER');
await denied(()=>call(1,'save',{id:a.id,revision:0,answers:{999:1},flags:[],cursor:0}),'INVALID_ANSWER');
await denied(()=>call(1,'save',{id:a.id,revision:0,answers:{},flags:[999],cursor:0}),'INVALID_FLAG');
a=await call(1,'save',{id:a.id,revision:0,answers:{18:bank[18].data.questions[17].answer},flags:[18],cursor:17});
await denied(()=>call(1,'save',{id:a.id,revision:0,answers:{},flags:[],cursor:0}),'EXAM_CONFLICT_RELOAD');
ok((await call(1,'get',{id:a.id})).answers['18']===bank[18].data.questions[17].answer);
await db.query("update hwarang_exam_attempts set deadline=now()-interval '1 second' where id=$1",[a.id]);
a=await call(1,'save',{id:a.id,revision:a.revision,answers:{},flags:[],cursor:0});
ok(a.status==='submitted');ok(a.result.sections.every(s=>s.score===4));
// Exact 60/59 boundary, independent section pass and no client score input.
const sample=bank[18];
for(const targetScore of [59,60]){
 let attempt=await call(1,'start',{id:uid(serial++),exam_id:sample.id,track:'main',mode:'practice'});
 let answers={};let remaining=targetScore;
 if(targetScore%3===1){const q=sample.data.questions[17];answers[18]=q.answer;remaining-=4;}
 // 59 cannot be formed from 3-point items + one 4-point item; check 58 vs 60 instead.
 if(targetScore===59){remaining=54;answers[18]=sample.data.questions[17].answer;}
 for(const q of sample.data.questions){if(q.number<=33&&q.number!==18&&remaining>=3){answers[q.number]=q.answer;remaining-=3;}}
 attempt=await call(1,'save',{id:attempt.id,revision:0,answers,flags:[],cursor:0});attempt=await call(1,'submit',{id:attempt.id,revision:attempt.revision});ok(attempt.result.passed===(targetScore===60));ok(attempt.deadline===null);
}
ok((await call(3,'team')).every(r=>r.user_id===uid(1)||r.user_id===uid(3)));ok((await call(4,'roster')).length===5);
await db.query('update hwarang_app_access set is_enabled=false where user_id=$1',[uid(2)]);await denied(()=>call(2,'catalog'),'EXAM_ACCESS_DENIED');
await db.query('update profiles set is_active=false where id=$1',[uid(1)]);await denied(()=>call(1,'list'),'EXAM_ACCESS_DENIED');
await db.exec('grant usage on schema public to anon,authenticated;set role anon;');await denied(()=>db.query('select * from hwarang_exam_bank'),'permission denied');await denied(()=>db.query('select public.hwarang_exam($1,$2,$3)',[uid(1),'catalog',{}]),'permission denied');await db.exec('reset role;set role authenticated;');await denied(()=>db.query('select * from hwarang_exam_attempts'),'permission denied');await db.exec('reset role;');
for(const family of ['life','nonlife'])for(const track of ['main','third','combined']){
 let r=await call(8,'random_start',{id:uid(serial++),family,track,mode:'exam'});
 const raw=(await db.query('select snapshot from hwarang_exam_attempts where id=$1',[r.id])).rows[0].snapshot;
 ok(new Set(raw.questions.map(q=>JSON.stringify([q.question,q.choices]))).size===raw.questions.length);
 for(const section of raw.sections)ok(raw.questions.filter(q=>section.numbers.includes(q.number)).reduce((n,q)=>n+q.points,0)===100);
 for(const q of raw.questions){const original=bank.find(b=>b.id===q.source_exam_id).data.questions.find(o=>o.number===q.source_number);for(const k of ['question','choices','answer','explanation','passage','table']){assert.deepEqual(q[k],original[k]);checks++};}
 ok(r.questions.every(q=>!('answer' in q)));
 r=await call(8,'submit',{id:r.id,revision:r.revision});const original=stable(r);
 let review=await call(8,'review_start',{id:uid(serial++),parent_id:r.id});
 ok(review.source_kind==='review'&&review.deadline===null);ok(review.questions.every(q=>!('answer' in q)));
 const q=raw.questions[0];review=await call(8,'save',{id:review.id,revision:review.revision,answers:{[q.number]:q.answer},flags:[],cursor:0});
 review=await call(8,'check',{id:review.id,revision:review.revision,number:q.number});ok(review.questions[0].answer===q.answer);ok(review.questions.slice(1).every(q=>!('answer' in q)));
 await denied(()=>call(8,'save',{id:review.id,revision:review.revision,answers:{[q.number]:99},flags:[],cursor:0}),'REVIEW_ALREADY_CHECKED');
 review=await call(8,'submit',{id:review.id,revision:review.revision});ok(review.result.sections[0].score===Math.round(100/review.questions.length));ok(stable(await call(8,'get',{id:r.id}))===original);
}
await db.exec('grant usage on schema public,private to service_role; grant select on profiles,organization_units,hwarang_app_access to service_role; grant execute on function private.can_user_view(uuid,uuid),private.is_org_descendant(uuid,uuid),public.get_hwarang_effective_permissions(uuid) to service_role; set role service_role;');
ok((await call(8,'roster')).length>0);ok((await call(8,'team')).length>0);await db.exec('reset role');
ok((await db.query("select private.exam_fingerprint($1::jsonb)=private.exam_fingerprint($2::jsonb) equal",[JSON.stringify({question:'가 나',choices:[{number:1,text:'보 기'}]}),JSON.stringify({question:'가\n나',choices:[{number:1,text:'보기'}]})])).rows[0].equal);
ok(!(await db.query("select private.exam_fingerprint($1::jsonb)=private.exam_fingerprint($2::jsonb) equal",[JSON.stringify({question:'100만원'}),JSON.stringify({question:'10만원'})])).rows[0].equal);
const report={checks,examTrackCombinations:108,engine:'PGlite PostgreSQL',productionDatabaseChanged:false,status:'passed'};console.log(JSON.stringify(report));await db.close();
