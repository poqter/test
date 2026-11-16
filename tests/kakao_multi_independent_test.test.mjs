import test from 'node:test';import assert from 'node:assert/strict';
import {makeTestWorker} from '../supabase/functions/hwarang-kakao-test/worker.mjs';
import {briefing} from '../supabase/functions/hwarang-kakao/message.mjs';
import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
const values={SUPABASE_URL:'https://test.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32),KAKAO_MULTI_ENABLED:'true'};
const req=()=>new Request(values.SUPABASE_URL+'/test',{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})});
async function run({duplicate=false,valid=true,timeout=false,persist=true,expired=false,long=false,weather=false}={}){
 let sends=0;const calls=[];const day=new Date(Date.now()+9*3600000).toISOString().slice(0,10);
 const cipher=await seal({access_token:'not-logged',expires_at:Date.now()+(expired?1000:900000),refresh_expires_at:Date.now()+9000000},values.KAKAO_MULTI_TOKEN_KEY,'owner',1);
 const handler=makeTestWorker(n=>values[n],async(u,i)=>{
  const body=i.body instanceof URLSearchParams?null:JSON.parse(i.body||'{}');calls.push([u,body]);
  if(u.endsWith('/kakao_test_claim'))return Response.json(duplicate?null:{id:'request',claim_token:'claim',owner_id:'owner',generation:1,day,encrypted_tokens:cipher,summary:{events:long?[{id:'e',title:'가'.repeat(300)}]:[],preferences:{weather_region_key:'seoul'}}});
  if(u.endsWith('/kakao_test_weather_claim'))return Response.json(weather?{status:'cached',region_name:'서울특별시',forecast:{status:'ok',day,low:null,high:15,morning:'맑음',afternoon:'흐림',issued_day:day,issued_time:'05:00'}}:{status:'unavailable',region_name:'서울특별시'});
  if(u.endsWith('/kakao_test_validate'))return Response.json(valid);
  if(u.endsWith('/kakao_test_complete'))return Response.json(body.p_status==='accepted'?persist:true);
  if(u==='https://kapi.kakao.com/v2/api/talk/memo/default/send'){
   sends++;const t=JSON.parse(i.body.get('template_object'));assert.ok(!t.text.includes('테스트'));assert.ok(t.text.startsWith('🗓'));assert.equal(t.text,briefing(day,[],false,weather?{status:'ok',day,region_name:'서울특별시',low:null,high:15,morning:'맑음',afternoon:'흐림',issued_day:day,issued_time:'05:00'}:{status:'unavailable',region_name:'서울특별시'}).join('\n'));assert.ok(t.text.length<=200);
   if(timeout)throw Error('Ambiguous response');return Response.json({result_code:0});
  }
  throw Error('Unexpected endpoint '+u);
 });
 const result=await handler(req());return {result,sends,calls};
}
test('single test sends once and does not touch regular jobs, preferences or cron',async()=>{const r=await run({weather:true});assert.equal(r.result.status,200);assert.equal(r.sends,1);assert.equal(r.calls.at(-1)[1].p_status,'accepted');assert.ok(!r.calls.some(([u])=>/reserve|service_claim|preferences|tick|rotate|continue/.test(u)));});
test('duplicate consumed ticket cannot send again',async()=>{const r=await run({duplicate:true});assert.equal(r.result.status,409);assert.equal(r.sends,0);assert.equal(r.calls.length,1);});
test('authorization changes and expired credentials fail before sending',async()=>{for(const config of [{valid:false},{expired:true},{long:true}]){const r=await run(config);assert.equal(r.sends,0);assert.equal(r.calls.at(-1)[1].p_status,'failed');}});
test('timeout or lost acceptance persistence is uncertain and never retried',async()=>{for(const config of [{timeout:true},{persist:false}]){const r=await run(config);assert.equal(r.sends,1);assert.equal(r.result.status,503);assert.equal(r.calls.at(-1)[1].p_status,'uncertain');}});
test('weather unavailable still clearly reports missing weather',async()=>{assert.equal((await run()).sends,1);});
test('missing authorization and disabled gate cannot query credentials',async()=>{for(const disabled of [false,true]){let calls=0;const h=makeTestWorker(n=>n==='KAKAO_MULTI_ENABLED'&&disabled?'false':values[n],()=>{calls++;throw Error('No call');});const r=await h(new Request(values.SUPABASE_URL,{method:'POST',body:'{}'}));assert.equal(r.status,disabled?503:401);assert.equal(calls,0);}});
test('cached-only second test does not claim or fetch weather',async()=>{
 const day=new Date(Date.now()+9*3600000).toISOString().slice(0,10);let sends=0;
 const cipher=await seal({access_token:'t',expires_at:Date.now()+900000,refresh_expires_at:Date.now()+9000000},values.KAKAO_MULTI_TOKEN_KEY,'owner',1);
 const h=makeTestWorker(n=>values[n],async(u,i)=>{
  if(u.endsWith('/kakao_test_claim'))return Response.json({id:'r',owner_id:'owner',generation:1,claim_token:'c',day,encrypted_tokens:cipher,cached_weather_only:true,cached_weather:{status:'ok',day,region_name:'서울특별시',low:11,high:16,morning:'맑음',afternoon:'흐림',issued_day:day,issued_time:'02:00'},summary:{events:[],preferences:{weather_region_key:'seoul'}}});
  if(u.endsWith('/kakao_test_validate')||u.endsWith('/kakao_test_complete'))return Response.json(true);
  if(u.startsWith('https://kapi.kakao.com/')){sends++;return Response.json({result_code:0});}
  throw Error('Unexpected weather or regular request');
 });assert.equal((await h(req())).status,200);assert.equal(sends,1);
});
