// Build an isolated database and return the records actually visible to the manager.
import {PGlite} from './studio_db/node_modules/@electric-sql/pglite/dist/index.js';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const db = new PGlite();
const migration = name => db.exec(fs.readFileSync(new URL('../supabase/migrations/' + name, import.meta.url), 'utf8'));
const worker = '11111111-1111-4111-8111-111111111111';
const manager = '22222222-2222-4222-8222-222222222222';
const outside = '33333333-3333-4333-8333-333333333333';
const day = '2025-11-18';
const moved = '2025-11-19';
const role = async id => db.exec(`reset role; set role authenticated; set request.jwt.claim.sub='${id}'`);
const select = async (sql, params=[]) => (await db.query(sql, params)).rows;

await db.exec(`
 create role anon; create role authenticated; create role service_role;
 create schema private; create schema auth;
 create function auth.uid() returns uuid language sql as $$select current_setting('request.jwt.claim.sub',true)::uuid$$;
 create function auth.jwt() returns jsonb language sql as $$select jsonb_build_object('session_id',auth.uid())$$;
 create table auth.sessions(id uuid primary key,user_id uuid);
 create table organization_units(id uuid primary key,parent_id uuid,is_active boolean default true);
 create table profiles(id uuid primary key,organization_unit_id uuid,display_name text,login_id text,position_code text,role text,is_active boolean default true);
 create table hwarang_permissions(permission_code text,app_code text,group_label text,display_name text,description text,sort_order int,default_granted boolean);
 create table hwarang_app_access(user_id uuid,app_code text,is_enabled boolean);
 create table hwarang_account_security(user_id uuid);
 create function get_hwarang_effective_permissions(uuid) returns table(permission_code text) language sql as $$select 'workspace.sales_activity'::text$$;
 create table sales_contracts(owner uuid,day date); create table sales_empty_days(owner uuid,day date);
 create table sales_team_assignments(member uuid,leader uuid); create table sales_deputy_assignments(member uuid,leader uuid);
 insert into organization_units(id) values ('${worker}'),('${outside}');
 insert into profiles(id,organization_unit_id,display_name,position_code,role) values
 ('${worker}','${worker}','직원','fp','user'),('${manager}','${worker}','관리자','branch_manager','user'),
 ('${outside}','${outside}','범위 밖','fp','user');
 insert into auth.sessions select id,id from profiles;
 insert into hwarang_app_access select id,'workspace',true from profiles;
 grant usage on schema auth,private to authenticated;
`);
await migration('30_Sales_Activity.sql');
await migration('31_Sales_Activity_Notifications.sql');
await migration('20261109182715_activity_report_workflow.sql');
await db.exec('alter table sales_events add column deleted_at timestamptz');
await migration('20261109204457_support_request_recipient.sql');
await migration('20261111034813_activity_daily_period_sync.sql');
await migration('20261118155101_activity_signal_targets.sql');

const save = async (date, ap, base, draft, submit, help='') => {
    const detail = date === day && ap > 0;
    const counts = {TA:detail ? 2 : 0, AP:ap, PC:detail ? 3 : 0, CS:detail ? 1 : 0, '약속 확보':detail ? 4 : 0, '청약':detail ? 1 : 0};
    const data = {counts, no_activity: ap === 0, help, help_recipient: help ? manager : null};
    await db.query("select public.sales_save_report($1,'일일',$2::jsonb,$3,$4,$5)",[date, JSON.stringify(data),base,draft,submit]);
};
async function version(topic, date) {
    const rows = await select('select version from sales_activity_signals where owner=$1 and topic=$2 and day=$3',[worker,topic,date]);
    return Number(rows[0]?.version ?? 0);
}
const snapshots = [];
async function capture(expectedVersion, expectedNotices) {
    await role(manager);
    assert.equal(await version('sales_reports',day), expectedVersion);
    const notices = await select('select id from sales_notices where recipient=$1 and report is not null',[manager]);
    assert.equal(notices.length, expectedNotices);
    const reports = await select('select id,owner,day::text,period,data,revision,submitted from sales_reports order by day');
    assert.ok(reports.every(r => r.owner === worker));
    snapshots.push(reports);
    await role(worker);
}
await role(outside);
await save(day,99,0,0,true);
await role(worker);
await save('2025-11-03',3,0,0,true);
await save('2025-11-17',0,0,0,true);
await save(day,5,0,0,true,'지원 A');
await capture(1,1);
await save(day,9,1,0,false,'지원 B');
await capture(1,1);
await save(day,9,1,1,true,'지원 B');
await capture(2,2);
await assert.rejects(() => save(day,20,1,0,true), /변경/);
assert.equal(await version('sales_reports',day),2);

await db.query("insert into sales_events(id,unit,day,kind,title,help,help_recipient) values($1,$1,$2,'AP','기존','동행 요청',$3)",[worker,day,manager]);
assert.equal(await version('sales_events',day),1);
await db.query("update sales_events set title='수정' where id=$1",[worker]);
assert.equal(await version('sales_events',day),2);
await db.query('update sales_events set day=$1 where id=$2',[moved,worker]);
assert.equal(await version('sales_events',day),3);
assert.equal(await version('sales_events',moved),1);
await role(manager);
assert.equal((await select('select id from sales_notices where event=$1',[worker])).length,1);
await db.exec('reset role');
await db.query('delete from sales_notices where event=$1',[worker]);
await db.query('delete from sales_events where id=$1',[worker]);
assert.equal(await version('sales_events',moved),2);
await role(worker);
const draftDay = '2025-11-20';
await save(draftDay,1,0,0,false);
await save(draftDay,2,1,0,false);
assert.equal(await version('sales_reports',draftDay),2);
await role(manager);
assert.equal((await select('select id from sales_reports where day=$1',[draftDay])).length,0);
await role(worker);
await save(draftDay,2,2,0,true);
assert.equal(await version('sales_reports',draftDay),3);
await db.close();
process.stdout.write(JSON.stringify({worker, snapshots}));
