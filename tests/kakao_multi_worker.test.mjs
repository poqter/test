import test from 'node:test';import assert from 'node:assert/strict';import {makeWorker} from '../supabase/functions/hwarang-kakao/worker.mjs';import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
const values={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'server',KAKAO_MULTI_ENABLED:'true',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32)};
const env=n=>values[n];const request=()=>new Request(values.SUPABASE_URL+'/tick',{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})});
test('unauth tick cannot read queue',async()=>{let calls=0;const h=makeWorker(env,()=>{calls++;throw Error('unexpected')});assert.equal((await h(new Request(values.SUPABASE_URL+'/tick',{method:'POST'}))).status,401);assert.equal(calls,0)});
test('cost gate off does not touch jobs or API',async()=>{const calls=[];const h=makeWorker(env,async u=>{calls.push(u);return Response.json(u.endsWith('/kakao_service_consume_tick')?true:{enabled:false})});assert.equal((await h(request())).status,200);assert.equal(calls.length,2)});
async function run({allowed=true,apiFails=false}={}){const calls=[];const cipher=await seal({access_token:'token',refresh_token:'refresh',expires_at:Date.now()+900000,refresh_expires_at:Date.now()+9000000},values.KAKAO_MULTI_TOKEN_KEY,'owner',1);const h=makeWorker(env,async(u,i)=>{calls.push([u,i.body]);if(u.endsWith('/kakao_service_consume_tick'))return Response.json(true);if(u.endsWith('/kakao_service_gate'))return Response.json({enabled:true});if(u.endsWith('/kakao_service_due'))return Response.json([]);if(u.endsWith('/kakao_service_expire'))return Response.json(true);if(u.endsWith('/kakao_service_pending'))return Response.json([{id:'job'}]);if(u.endsWith('/kakao_service_tick_enter'))return Response.json(true);if(u.endsWith('/kakao_service_claim'))return Response.json({job_id:'job',claim_token:'claim',owner_id:'owner',generation:1,body:'일정',encrypted_tokens:cipher});if(u.endsWith('/kakao_service_validate_claim'))return Response.json(allowed);if(u.endsWith('/kakao_service_complete'))return Response.json(true);if(u.endsWith('/kakao_service_continue'))return Response.json(false);if(u==='https://kapi.kakao.com/v2/api/talk/memo/default/send'){if(apiFails)throw Error('timeout');return Response.json({result_code:0});}throw Error('unexpected '+u)});await h(request());return calls;}
test('only allowed memo endpoint invoked; one accepted record',async()=>{const calls=await run();assert.equal(calls.filter(([u])=>u.startsWith('https://kapi.')).length,1);assert.equal(JSON.parse(calls.findLast(([u])=>u.endsWith('/kakao_service_complete'))[1]).p_status,'accepted')});
test('preflight revocation blocks Kakao call',async()=>{const calls=await run({allowed:false});assert.equal(calls.filter(([u])=>u.startsWith('https://kapi.')).length,0)});
test('ambiguous network result stored uncertain with no retry',async()=>{const calls=await run({apiFails:true});assert.equal(calls.filter(([u])=>u.startsWith('https://kapi.')).length,1);assert.equal(JSON.parse(calls.findLast(([u])=>u.endsWith('/kakao_service_complete'))[1]).p_status,'uncertain')});
test('consumed or expired tick ticket cannot read queue',async()=>{const calls=[];const h=makeWorker(env,async u=>{calls.push(u);return Response.json(false)});assert.equal((await h(request())).status,401);assert.equal(calls.length,1);assert.ok(calls[0].endsWith('/kakao_service_consume_tick'))});
test('26th job deferred by bounded tick and continuation requested only after progress',async()=>{
 let sends=0,continuation;const cipher=await seal({access_token:'token',refresh_token:'r',expires_at:Date.now()+900000,refresh_expires_at:Date.now()+9000000},values.KAKAO_MULTI_TOKEN_KEY,'owner',1);
 const h=makeWorker(env,async(u,i)=>{const p=i.body?JSON.parse(i.body instanceof URLSearchParams?'{}':i.body):{};
 if(u.endsWith('/kakao_service_consume_tick')||u.endsWith('/kakao_service_tick_enter')||u.endsWith('/kakao_service_expire')||u.endsWith('/kakao_service_validate_claim')||u.endsWith('/kakao_service_complete'))return Response.json(true);
 if(u.endsWith('/kakao_service_gate'))return Response.json({enabled:true});if(u.endsWith('/kakao_service_due'))return Response.json([]);
 if(u.endsWith('/kakao_service_pending'))return Response.json(Array.from({length:26},(_,id)=>({id:String(id)})));
 if(u.endsWith('/kakao_service_claim'))return Response.json({job_id:p.p_job_id,claim_token:'claim',owner_id:'owner',generation:1,body:'일정',encrypted_tokens:cipher});
 if(u.endsWith('/kakao_service_continue')){continuation=p;return Response.json(true)}
 if(u.startsWith('https://kapi.kakao.com/')){sends++;return Response.json({result_code:0})}throw Error('unexpected');});
 const r=await h(request());assert.equal(r.status,200);assert.equal(sends,25);assert.equal(continuation.p_progress,true);assert.match(continuation.p_tick_hash,/^[a-f0-9]{64}$/);
});
test('empty-day skip is progress so remaining subscribers get a continuation',async()=>{
 let continued=false,reserved=0;
 const h=makeWorker(env,async(u,i)=>{
  if(u.endsWith('/kakao_service_consume_tick')||u.endsWith('/kakao_service_tick_enter')||u.endsWith('/kakao_service_expire'))return Response.json(true);
  if(u.endsWith('/kakao_service_gate'))return Response.json({enabled:true});
  if(u.endsWith('/kakao_service_due'))return Response.json(Array.from({length:25},(_,n)=>({owner_id:String(n),day:'2026-11-16',generation:1,scope_hash:'hash',summary:{events:[],empty_explicit:true}})));
  if(u.endsWith('/kakao_service_reserve')){reserved++;return Response.json({batch_id:String(reserved),status:'empty_day_skipped'});}
  if(u.endsWith('/kakao_service_pending'))return Response.json([]);
  if(u.endsWith('/kakao_service_continue')){continued=JSON.parse(i.body).p_progress;return Response.json(true);}
  throw Error('unexpected');
 });
 assert.equal((await h(request())).status,200);assert.equal(reserved,25);assert.equal(continued,true);
});
test('definite consent withdrawal pauses connection; timeout does not',async()=>{
 const calls=[];const cipher=await seal({access_token:'token',refresh_token:'r',expires_at:Date.now()+900000,refresh_expires_at:Date.now()+9000000},values.KAKAO_MULTI_TOKEN_KEY,'owner',1);
 const h=makeWorker(env,async(u,i)=>{calls.push([u,i.body]);
  if(u.endsWith('/kakao_service_consume_tick')||u.endsWith('/kakao_service_tick_enter')||u.endsWith('/kakao_service_expire')||u.endsWith('/kakao_service_validate_claim')||u.endsWith('/kakao_service_complete')||u.endsWith('/kakao_service_require_reauth'))return Response.json(true);
  if(u.endsWith('/kakao_service_gate'))return Response.json({enabled:true});if(u.endsWith('/kakao_service_due'))return Response.json([]);
  if(u.endsWith('/kakao_service_pending'))return Response.json([{id:'job'}]);
  if(u.endsWith('/kakao_service_claim'))return Response.json({job_id:'job',claim_token:'claim',owner_id:'owner',generation:1,body:'일정',encrypted_tokens:cipher});
  if(u.endsWith('/kakao_service_continue'))return Response.json(false);
  if(u.startsWith('https://kapi.kakao.com/'))return Response.json({code:-402},{status:403});throw Error('unexpected');
 });
 assert.equal((await h(request())).status,200);
 assert.equal(calls.filter(([u])=>u.endsWith('/kakao_service_require_reauth')).length,1);
 assert.equal(JSON.parse(calls.find(([u])=>u.endsWith('/kakao_service_complete'))[1]).p_status,'failed');
 const ambiguous=await run({apiFails:true});assert.equal(ambiguous.filter(([u])=>u.endsWith('/kakao_service_require_reauth')).length,0);
});
for(const mode of ['missing_region','cache','cache_error'])test('weather integration preserves schedules: '+mode,async()=>{
 const calls=[],manifests=[];let weatherCalls=0;
 const h=makeWorker(n=>n==='KMA_SERVICE_KEY'?(mode==='missing_region'?'':'synthetic-key'):env(n),async(u,i)=>{
  calls.push(String(u));
  if(u.endsWith('/kakao_service_consume_tick')||u.endsWith('/kakao_service_tick_enter')||u.endsWith('/kakao_service_expire')||u.endsWith('/kakao_service_continue'))return Response.json(true);
  if(u.endsWith('/kakao_service_gate'))return Response.json({enabled:true});
  if(u.endsWith('/kakao_service_due'))return Response.json([1,2].map(n=>({owner_id:String(n),day:'2026-11-16',generation:1,scope_hash:'hash',summary:{events:[{id:String(n),title:'각자상담'+n}],preferences:{weather_region_key:mode==='missing_region'?null:'web:1100000000'}}})));
  if(u.endsWith('/kakao_service_weather_claim')){weatherCalls++;if(mode==='cache_error')throw Error('unavailable');return Response.json({status:'cached',region_name:'서울 송파구',forecast:{status:'ok',day:'2026-11-16',low:2,high:10,rain_probability:20,condition:'맑음',issued_day:'2026-11-16',issued_time:'05:00'}});}
  if(u.endsWith('/kakao_service_reserve')){manifests.push(JSON.parse(i.body).p_parts.join('\n'));return Response.json({batch_id:String(manifests.length)});}
  if(u.endsWith('/kakao_service_pending'))return Response.json([]);
  throw Error('unexpected request');
 });
 assert.equal((await h(request())).status,200);assert.equal(manifests.length,2);assert.ok(manifests[0].includes('각자상담1'));assert.ok(manifests[1].includes('각자상담2'));
 assert.equal(weatherCalls,mode==='missing_region'?0:1);assert.ok(calls.every(u=>u.startsWith(values.SUPABASE_URL)));
 if(mode==='cache')assert.ok(manifests[0].includes('출처: 기상청'));else assert.ok(manifests[0].includes('확인하지 못했습니다'));
});
