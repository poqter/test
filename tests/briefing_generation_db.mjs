import assert from 'node:assert/strict';
import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {handle} from '../public_reader/worker.js';
import {PGlite} from './exams/node_modules/@electric-sql/pglite/dist/index.js';

const sql = name => fs.readFileSync(new URL('../supabase/migrations/' + name, import.meta.url), 'utf8');
const migrate = sql('20261119165753_separate_briefing_generation.sql');
const state = async db => (await db.query("select generation_enabled from public.hwarang_briefing_operating_policy where policy_key='WORKSPACE'")).rows[0].generation_enabled;

export async function verifyBriefingGeneration(db, admin, member) {
    await db.exec(`reset role;
        create schema storage;
        create table storage.buckets(id text primary key, name text, public boolean, file_size_limit bigint, allowed_mime_types text[]);
        create table storage.objects(bucket_id text, name text, created_at timestamptz);`);
    for (const name of [
        '16_Briefing_Engine_V1_6_Action_Intelligence_FINAL.sql', '20_Briefing_Daily_Operation.sql',
        '21_Briefing_Launch_Readiness.sql', '22_Briefing_Article_Release.sql',
        '20261026061737_briefing_share_lifecycle.sql', '20261026064021_briefing_shared_content.sql',
    ]) await db.exec(sql(name));

    // Both possible cutover values must survive. Run the OFF upgrade on a separate copy.
    const off = new PGlite({loadDataDir: await db.dumpDataDir('none')});
    try {
        await off.exec('update public.hwarang_ai_runtime_config set service_enabled=false where config_id=1');
        await off.exec(migrate);
        assert.equal(await state(off), false);
    } finally {
        await off.close();
    }

    await db.exec('update public.hwarang_ai_runtime_config set service_enabled=true where config_id=1');
    const token = randomUUID(), revision = randomUUID(), briefing = randomUUID();
    const day = '2026-11-19';
    const packet = {schema:'hwarang-share-v3', briefing_date:day, body:{title:'공개 브리핑 검증'},
        asset_version:'a'.repeat(24),rendered_html:'<main>공개 브리핑 검증</main>'};
    await db.query("update public.hwarang_briefing_operating_policy set external_sharing_approved=true where policy_key='WORKSPACE'");
    await db.query("insert into public.hwarang_briefings(id,profile_code,briefing_date,briefing_type) values ($1,'INSURANCE',$2,'MORNING')",[briefing,day]);
    await db.query("insert into public.hwarang_briefing_revisions(id,briefing_id,revision_no,revision_type,validation_status,coverage_status) values ($1,$2,1,'initial','ok','healthy')",[revision,briefing]);
    await db.query("insert into public.hwarang_briefing_snapshots(revision_id,content_payload,qa_payload) values ($1,$2,$3)",[revision,{issues:[{},{}]},{internal_body_ready:true,public_body_ready:true}]);
    await db.query('select public.hwarang_publish_briefing($1,$2,$3)',[briefing,revision,admin]);
    const share = t => db.query('select public.hwarang_register_combined_share($1,$2,$3,$4)',[t,member,[revision],packet]);
    await share(token);
    const read = async t => (await db.query('select public.hwarang_read_public_briefing($1) as packet',[t])).rows[0].packet;
    const customerPage = t => handle(new Request('https://reader.example.invalid/?token=' + t), {
        env: name => name === 'SUPABASE_URL' ? 'https://fixture.example.invalid' : 'synthetic',
        fetcher: async (url, init) => {
            assert.equal(new URL(url).pathname,'/rest/v1/rpc/hwarang_read_public_briefing');
            return Response.json(await read(JSON.parse(init.body).p_token));
        },
    });
    const published = async () => (await db.query(`select s.content_payload from public.hwarang_briefings b
        join public.hwarang_briefing_snapshots s on s.revision_id=b.current_published_revision_id where b.id=$1`,[briefing])).rows[0];
    const before = await published();
    assert.deepEqual(before.content_payload, {issues:[{},{}]});
    assert.deepEqual(await read(token), packet);
    const page = await customerPage(token);
    assert.equal(page.status,200);
    const originalHtml = await page.text();
    assert.ok(originalHtml.includes('공개 브리핑 검증'));
    await db.exec(migrate);
    assert.equal(await state(db), true);
    const toggle = (actor, previous, enabled) => db.query('select public.admin_set_briefing_service_enabled($1,$2,$3)',[actor,previous,enabled]);
    const reserve = async kind => (await db.query('select public.hwarang_reserve_briefing_request($1,$2) as ok',[day,kind])).rows[0].ok;
    const budget = async () => (await db.query('select web_requests,analysis_requests from public.hwarang_briefing_daily_budget where briefing_date=$1',[day])).rows[0];
    await db.exec('set role service_role');
    const auditCount = async () => (await db.query("select count(*)::int as n from public.hwarang_admin_audit_log where actor_user_id=$1 and action='briefing_service_updated'",[admin])).rows[0].n;
    const previousAudits = await auditCount();
    assert.equal(await reserve('web'), true);
    assert.equal(await reserve('analysis'), true);
    await assert.rejects(()=>toggle(member,true,false),/SUPER_ADMIN_REQUIRED/);
    await toggle(admin,true,false);
    await assert.rejects(()=>toggle(admin,true,false),/BRIEFING_STATE_CHANGED/);
    await db.exec('reset role');
    await db.exec(migrate);
    assert.equal(await state(db), false);
    // Retired simulator settings are unavailable to the new reader, setter and reservation.
    await db.exec('alter table public.hwarang_ai_runtime_config rename to retired_ai_config; set role service_role');
    for (const kind of ['web','analysis']) await assert.rejects(()=>reserve(kind),/AI_SERVICE_DISABLED/);
    assert.deepEqual(await budget(),{web_requests:1,analysis_requests:1});
    assert.deepEqual(await published(), before);
    assert.deepEqual(await read(token), packet);
    const stoppedPage = await customerPage(token);
    assert.equal(stoppedPage.status,200);
    assert.equal(await stoppedPage.text(),originalHtml);
    const sharedWhileStopped = randomUUID();
    const parts = {
        content_id:'1'.repeat(64), weather_id:'2'.repeat(64), preview_id:'3'.repeat(64), reuse_key:'4'.repeat(64),
        content:{packet,html_template:'<p>__HW_IDENTITY_9e21__</p>'}, weather:{payload:{},rendered_html:''},
    };
    await db.query('select public.hwarang_prepare_preview($1)',[parts.preview_id]);
    const registered = await db.query('select public.hwarang_register_shared_link($1,$2,$3,$4,$5) as token',
        [sharedWhileStopped,member,[revision],{...packet,sender:{name:'검증',position:'FP'}},parts]);
    assert.equal(registered.rows[0].token,sharedWhileStopped);
    const expanded = await read(sharedWhileStopped);
    assert.deepEqual(expanded.body,packet.body);
    assert.equal(expanded.rendered_html,'<p>검증 FP</p>');
    assert.equal((await customerPage(sharedWhileStopped)).status,200);
    await toggle(admin,false,true);
    assert.equal(await state(db), true);
    assert.deepEqual(await read(token), packet);
    for(let i=1;i<6;i++) assert.equal(await reserve('web'),true);
    for(let i=1;i<4;i++) assert.equal(await reserve('analysis'),true);
    assert.equal(await reserve('web'),false);
    assert.equal(await reserve('analysis'),false);
    assert.equal(await auditCount(), previousAudits + 2);
    await db.query('update public.hwarang_briefing_public_shares set revoked_at=now() where token=$1',[token]);
    assert.equal(await read(token),null);
    assert.equal((await customerPage(token)).status,410);
    for (const role of ['anon','authenticated']) {
        await db.exec('reset role; set role '+role);
        await assert.rejects(()=>state(db),/permission denied/);
        await assert.rejects(()=>toggle(admin,true,false),/permission denied/);
        await assert.rejects(()=>reserve('web'),/permission denied/);
    }
    await db.exec('reset role');
    console.log('PASS briefing generation: migrate ON/OFF, preserve edits on replay, stop/resume, quotas, published content and shared links, role restrictions');
}
