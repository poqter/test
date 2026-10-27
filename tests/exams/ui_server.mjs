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
import http from 'node:http';
http.createServer(async(req,res)=>{let body='';for await(const c of req)body+=c;try{const p=JSON.parse(body);const r=await db.query('select public.hwarang_exam($1,$2,$3::jsonb) result',[p.p_actor,p.p_action,JSON.stringify(p.p_payload)]);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(r.rows[0].result));}catch(e){res.statusCode=400;res.end(JSON.stringify({error:e.message}));}}).listen(8138,'127.0.0.1',()=>console.log('ready'));
