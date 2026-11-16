// Offline worker contract tests. Database eligibility/locking is verified separately in SQL.
import test from 'node:test';import assert from 'node:assert/strict';
import {makeWelcomeWorker} from '../supabase/functions/hwarang-kakao-welcome/worker.mjs';
import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
import {briefing} from '../supabase/functions/hwarang-kakao/message.mjs';
const env={SUPABASE_URL:'https://offline.invalid',SUPABASE_SERVICE_ROLE_KEY:'synthetic',KAKAO_MULTI_ENABLED:'true',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32)};
const request=()=>new Request('https://offline.invalid/welcome',{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})});
async function fixture(options={}) {
 const now=Date.now(),weather={status:'unavailable',region_name:'서울'};
 const summary={events:options.empty?[]:[{id:'event',title:options.long?'긴 일정 😀 '.repeat(70):'상담',start_time:'09:00',end_time:'10:00',place:'사무실',status:'예정'}],empty_explicit:false,preferences:{weather_region_key:'web:1100000000',send_empty:false}};
 const expected=options.parts??briefing('2026-11-17',summary.events,false,weather);
 const job={id:'welcome',owner_id:'owner',day:'2026-11-17',generation:1,claim_token:'claim',summary,parts:options.parts??null,next_part:options.nextPart??1,expires_at:new Date(now+(options.deadlineMs??600000)).toISOString(),encrypted_tokens:await seal({access_token:'synthetic-access',refresh_token:'synthetic-refresh',expires_at:now+(options.tokenMs??3600000),refresh_expires_at:now+86400000},env.KAKAO_MULTI_TOKEN_KEY,'owner',1)};
 const calls=[],sends=[],completion=[],failures=[];let reservation,part=0,continuations=0;
 const fetcher=async(url,init)=>{
  if(url==='https://kapi.kakao.com/v2/api/talk/memo/default/send'){
   sends.push(JSON.parse(new URLSearchParams(init.body).get('template_object')).text);
   assert.equal(init.headers.Authorization,'Bearer synthetic-access');
   if(options.onSend)options.onSend();
   if(options.uncertainPart===part)throw Error('Synthetic lost response');
   if(options.reauthPart===part)return Response.json({code:-402},{status:403});
   return Response.json({result_code:0});
  }
  assert.ok(url.startsWith(env.SUPABASE_URL+'/rest/v1/rpc/'),'No external requests');
  const name=url.split('/').at(-1),args=JSON.parse(init.body);calls.push(name);
  switch(name){
   case 'kakao_welcome_claim':return Response.json(options.noClaim?null:job);
   case 'kakao_service_weather_claim':return Response.json({status:'unavailable',region_name:'서울'});
   case 'kakao_welcome_reserve':reservation=args.p_parts;return Response.json({reserved:true});
   case 'kakao_welcome_begin_part':part=args.p_part;return Response.json({claimed:true,body:expected[part-1]});
   case 'kakao_welcome_validate':return Response.json(options.revoked!==true);
   case 'kakao_welcome_complete_part':completion.push([args.p_part,args.p_status]);if(options.completionLostPart===args.p_part&&args.p_status==='accepted')throw Error('Synthetic storage response loss');return Response.json(true);
   case 'kakao_welcome_fail':failures.push(args.p_reason);return Response.json(true);
   case 'kakao_welcome_continue':continuations++;if(options.continueLost)throw Error('Synthetic enqueue response loss');return Response.json(true);
   default:throw Error('Unexpected RPC '+name);
  }
 };
 const worker=makeWelcomeWorker(n=>env[n],fetcher);
 const response=await worker(request());
 return {response,result:await response.json(),calls,sends,completion,failures,reservation,expected,continuations};
}
test('welcome exact regular-format multipart is reserved losslessly and sent in order',async()=>{
 const r=await fixture({long:true});assert.equal(r.response.status,200);assert.equal(r.result.accepted,true);assert.ok(r.expected.length>1);assert.deepEqual(r.reservation,r.expected);assert.deepEqual(r.sends,r.expected);assert.ok(r.sends.every(s=>s.length<=200));assert.deepEqual(r.completion,r.expected.map((_,i)=>[i+1,'accepted']));assert.equal(r.failures.length,0);
});
test('welcome duplicate/unavailable ticket does not read weather or send',async()=>{
 const r=await fixture({noClaim:true});assert.equal(r.response.status,409);assert.deepEqual(r.calls,['kakao_welcome_claim']);assert.equal(r.sends.length,0);
});
test('welcome revoked generation/permission preflight prevents any provider call',async()=>{
 const r=await fixture({revoked:true});assert.equal(r.sends.length,0);assert.deepEqual(r.completion,[[1,'failed']]);assert.deepEqual(r.failures,['setup_failed']);
});
test('welcome provider response uncertainty stops later parts and never retries',async()=>{
 const r=await fixture({long:true,uncertainPart:2});assert.equal(r.sends.length,2);assert.deepEqual(r.completion,[[1,'accepted'],[2,'uncertain']]);assert.deepEqual(r.failures,['outcome_uncertain']);assert.equal(r.result.accepted_parts,1);assert.equal(r.continuations,0);
});
test('welcome accepted response storage loss never sends the next part',async()=>{
 const r=await fixture({long:true,completionLostPart:2});assert.equal(r.sends.length,2);assert.deepEqual(r.completion,[[1,'accepted'],[2,'accepted'],[2,'uncertain']]);assert.equal(r.continuations,0);
});
test('welcome expiring credentials require reauthentication without refresh/rotation',async()=>{
 const r=await fixture({tokenMs:60000});assert.equal(r.sends.length,0);assert.deepEqual(r.failures,['reauth_required']);assert.deepEqual(r.calls,['kakao_welcome_claim','kakao_welcome_fail']);
});
test('welcome definite withdrawn-consent rejection fails and does not continue',async()=>{
 const r=await fixture({long:true,reauthPart:1});assert.equal(r.sends.length,1);assert.deepEqual(r.completion,[[1,'failed']]);assert.deepEqual(r.failures,['reauth_required']);assert.equal(r.continuations,0);
});
test('welcome continuation uses immutable existing manifest and skips accepted parts',async()=>{
 const parts=['already accepted','remaining 2','remaining 3'];const r=await fixture({parts,nextPart:2});assert.deepEqual(r.sends,parts.slice(1));assert.ok(!r.calls.includes('kakao_service_weather_claim'));assert.ok(!r.calls.includes('kakao_welcome_reserve'));
});
test('welcome 25-part bound enqueues continuation once without omitting manifest tail',async()=>{
 const parts=Array.from({length:30},(_,i)=>'part '+(i+1));const r=await fixture({parts});assert.equal(r.response.status,202);assert.deepEqual(r.sends,parts.slice(0,25));assert.equal(r.continuations,1);assert.equal(r.failures.length,0);
});
test('welcome lost continuation response does not requeue or cancel possibly queued work',async()=>{
 const r=await fixture({parts:Array.from({length:26},(_,i)=>'part '+i),continueLost:true});assert.equal(r.response.status,503);assert.equal(r.result.continuation,'unconfirmed');assert.equal(r.continuations,1);assert.equal(r.failures.length,0);
});
test('welcome 40-second bound continues only unsent parts',async()=>{
 const realNow=Date.now;let now=realNow();Date.now=()=>now;
 try{const r=await fixture({parts:['a','b','c'],onSend:()=>{now+=21000;}});assert.equal(r.sends.length,2);assert.equal(r.continuations,1);assert.equal(r.response.status,202);}finally{Date.now=realNow;}
});
test('welcome deadline blocks new attempts even if token still valid',async()=>{
 const r=await fixture({deadlineMs:-1});assert.equal(r.sends.length,0);assert.deepEqual(r.failures,['setup_failed']);
});
test('welcome disabled or malformed request cannot touch ledger',async()=>{
 let calls=0;const fetcher=()=>{calls++;throw Error('Forbidden');};
 assert.equal((await makeWelcomeWorker(()=>'',fetcher)(request())).status,503);
 assert.equal((await makeWelcomeWorker(n=>env[n],fetcher)(new Request('https://offline.invalid',{method:'POST',body:'{}'}))).status,401);assert.equal(calls,0);
});

test('welcome first-day confirmation includes empty schedule plus weather despite normal send_empty=false',async()=>{
 const r=await fixture({empty:true});assert.equal(r.result.accepted,true);assert.ok(r.sends.join('\n').includes('아직 등록된 일정이 없습니다.'));assert.ok(r.sends.join('\n').includes('날씨'));
});
