// Real worker with an offline transactional queue model. No provider/network calls.
// This checks bounded scheduling and contracts, not PostgreSQL lock implementation.
import test from 'node:test';import assert from 'node:assert/strict';
import {makeWorker} from '../supabase/functions/hwarang-kakao/worker.mjs';
import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function model({implementation=makeWorker,owners=20,parts=5,sendMs=1,uncertain=null,storageLost=null,revoked=null,atomic=false,claimStorageFail=null,rotateRejected=null,onSend=null}={}){
 const env={SUPABASE_URL:'https://offline.invalid',SUPABASE_SERVICE_ROLE_KEY:'synthetic',KAKAO_MULTI_ENABLED:'true',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32),KAKAO_REST_API_KEY:'synthetic-client',KAKAO_CLIENT_SECRET:'synthetic-secret'};
 const jobs=[],attempts=[],rpcCalls=[],active=new Set();let peak=0,inFlight=0,ticks=0,units=0;
 for(let n=0;n<owners;n++){
  const owner='owner'+n,cipher=await seal({access_token:owner,refresh_token:'synthetic',expires_at:Date.now()+(owner===rotateRejected?10000:3600000),refresh_expires_at:Date.now()+86400000},env.KAKAO_MULTI_TOKEN_KEY,owner,1);
  for(let part=1;part<=parts;part++)jobs.push({id:owner+'-'+part,owner_id:owner,part,body:owner+' part '+part,status:'reserved',encrypted_tokens:cipher});
 }
 const claim=id=>{const j=jobs.find(j=>j.id===id);if(!j||j.status!=='reserved'||jobs.some(x=>x.owner_id===j.owner_id&&(x.status==='sending'||(x.part<j.part&&x.status!=='accepted'))))return {claimed:false};j.status='sending';return {...j,job_id:j.id,claim_token:'claim-'+j.id,generation:1};};
 const fetcher=async(url,init)=>{
  if(url==='https://kapi.kakao.com/v2/api/talk/memo/default/send'){
   const text=JSON.parse(new URLSearchParams(init.body).get('template_object')).text,j=jobs.find(j=>j.body===text);
   assert.ok(j);assert.equal(j.status,'sending');assert.equal(init.headers.Authorization,'Bearer '+j.owner_id);
   assert.ok(!active.has(j.owner_id),'Only one sending part per owner');active.add(j.owner_id);inFlight++;peak=Math.max(peak,inFlight);attempts.push(j.id);
   try{if(onSend)onSend();await pause(sendMs);if(j.id===uncertain)throw Error('Response lost');return Response.json({result_code:0});}finally{active.delete(j.owner_id);inFlight--;}
  }
  if(url==='https://kauth.kakao.com/oauth/token')return Response.json({access_token:'rotated',expires_in:3600});
  assert.ok(url.startsWith(env.SUPABASE_URL+'/rest/v1/rpc/'));const name=url.split('/').at(-1),a=JSON.parse(init.body);rpcCalls.push([name,a]);
  switch(name){
   case 'kakao_service_consume_tick':ticks++;return Response.json(true);
   case 'kakao_service_gate':return Response.json({enabled:true});
   case 'kakao_service_tick_enter':units++;return Response.json(true);
   case 'kakao_service_expire':return Response.json(true);
   case 'kakao_service_due':return Response.json([]);
   case 'kakao_service_pending':return Response.json(jobs.filter(j=>j.status==='reserved').sort((a,b)=>a.part-b.part||a.owner_id.localeCompare(b.owner_id)).slice(0,a.p_limit).map(j=>({id:j.id,owner_id:j.owner_id,part:j.part,...(atomic?{atomic_claim:true}:{})})));
   case 'kakao_service_claim':if(a.p_job_id===claimStorageFail)throw Error('Storage unavailable');return Response.json(claim(a.p_job_id));
   case 'kakao_service_begin_job':units++;return Response.json(claim(a.p_job_id));
   case 'kakao_service_rotate':return Response.json(a.p_owner!==rotateRejected);
   case 'kakao_service_validate_claim':return Response.json(a.p_job_id!==revoked);
   case 'kakao_service_complete':{
    const j=jobs.find(j=>j.id===a.p_job_id);if(j.status!=='sending')return Response.json(false);
    j.status=a.p_status;if(a.p_status!=='accepted')for(const x of jobs)if(x.owner_id===j.owner_id&&x.status==='reserved')x.status='cancelled';
    if(j.id===storageLost&&a.p_status==='accepted')throw Error('Completion response lost');return Response.json(true);
   }
   case 'kakao_service_continue':return Response.json(false);
   default:throw Error('Unexpected RPC '+name);
  }
 };
 const worker=implementation(n=>env[n],fetcher);
 const tick=()=>worker(new Request(env.SUPABASE_URL,{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})}));
 const verify=()=>{assert.equal(new Set(attempts).size,attempts.length);const order=new Map();for(const id of attempts){const j=jobs.find(j=>j.id===id);assert.equal(j.part,(order.get(j.owner_id)||0)+1);order.set(j.owner_id,j.part);}assert.equal(inFlight,0);};
 return {jobs,attempts,rpcCalls,tick,verify,stats:()=>({peak,ticks,units})};
}
for(const sendMs of [1,15])test(`bounded owner pool drains 20 x 5 parts at simulated provider delay ${sendMs}ms`,async()=>{
 const m=await model({sendMs});for(let n=0;n<10&&m.jobs.some(j=>j.status==='reserved');n++)assert.equal((await m.tick()).status,200);
 m.verify();assert.equal(m.attempts.length,100);assert.ok(m.jobs.every(j=>j.status==='accepted'));assert.equal(m.stats().peak,3);
});
test('uncertain part closes only that owner stale queue and preserves other owners',async()=>{
 const m=await model({owners:3,uncertain:'owner0-2'});await m.tick();m.verify();assert.equal(m.attempts.filter(id=>id.startsWith('owner0-')).length,2);assert.equal(m.rpcCalls.filter(([name,a])=>name==='kakao_service_claim'&&a.p_job_id==='owner0-3').length,0);assert.ok(m.jobs.filter(j=>j.owner_id!=='owner0').every(j=>j.status==='accepted'));
});
test('overlapping workers rely on atomic claims and never double-send a part',async()=>{
 const m=await model({owners:3,sendMs:5});await Promise.all([m.tick(),m.tick()]);for(let n=0;n<10&&m.jobs.some(j=>j.status==='reserved');n++)await m.tick();m.verify();assert.equal(m.attempts.length,15);
});
test('a revoked owner is never sent; other owners keep their own tokens',async()=>{
 const m=await model({owners:3,revoked:'owner0-1'});await m.tick();m.verify();assert.ok(m.attempts.every(id=>!id.startsWith('owner0-')));assert.equal(m.attempts.length,10);
});
test('lost completion response stops this tick owner tail without retrying accepted part',async()=>{
 const m=await model({owners:3,storageLost:'owner0-2'});await m.tick();m.verify();assert.deepEqual(m.attempts.filter(id=>id.startsWith('owner0-')),['owner0-1','owner0-2']);assert.equal(m.stats().peak,3);
});
test('combined begin RPC replaces enter+claim only when DB advertises support',async()=>{
 const m=await model({owners:3,atomic:true});await m.tick();m.verify();assert.equal(m.attempts.length,15);assert.equal(m.rpcCalls.filter(([n])=>n==='kakao_service_begin_job').length,15);assert.equal(m.rpcCalls.filter(([n])=>n==='kakao_service_claim').length,0);assert.equal(m.rpcCalls.filter(([n])=>n==='kakao_service_tick_enter').length,1);
});

test('claim RPC failure waits for all already-started owners before returning',async()=>{
 const m=await model({owners:3,sendMs:15,claimStorageFail:'owner0-1'});assert.equal((await m.tick()).status,503);m.verify();
});
test('rotation CAS refusal never uses rotated token and only closes that owner',async()=>{
 const m=await model({owners:3,rotateRejected:'owner0'});await m.tick();m.verify();assert.ok(m.attempts.every(id=>!id.startsWith('owner0-')));assert.equal(m.attempts.length,10);
});
test('40-second cutoff starts no new owner work after bound and awaits in-flight work',async()=>{
 const originalNow=Date.now;let now=originalNow();Date.now=()=>now;
 try{const m=await model({owners:20,onSend:()=>{now+=21000;}});await m.tick();m.verify();assert.ok(m.attempts.length>0&&m.attempts.length<100);assert.ok(m.stats().peak<=3);}finally{Date.now=originalNow;}
});
