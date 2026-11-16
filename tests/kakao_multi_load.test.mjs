// Offline load model: real worker/crypto, mocked transactional RPC contract and provider.
// Does NOT prove PostgreSQL locking, Edge startup latency or real-world delivery timing.
import test from 'node:test';
import assert from 'node:assert/strict';
import {makeWorker} from '../supabase/functions/hwarang-kakao/worker.mjs';
import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';

async function simulate({rpcMs=10,sendMs=20,uncertainId=null,completionLostId=null}={}) {
 const originalNow=Date.now;let now=Date.UTC(2026,10,17,23,0),start=now;
 Date.now=()=>now;
 try {
  const env={SUPABASE_URL:'https://offline.invalid',SUPABASE_SERVICE_ROLE_KEY:'synthetic',KAKAO_MULTI_ENABLED:'true',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32)};
  const jobs=[],attempts=[],claimed=[],partsByOwner=new Map();let ticks=0,continued=false,units=0;
  for(let owner=0;owner<20;owner++) {
   const ownerId=`owner-${owner}`;
   const cipher=await seal({access_token:ownerId,refresh_token:'synthetic',expires_at:start+3600000,refresh_expires_at:start+86400000},env.KAKAO_MULTI_TOKEN_KEY,ownerId,1);
   for(let part=1;part<=5;part++)jobs.push({id:`${ownerId}-${part}`,owner_id:ownerId,part,body:`${ownerId} part ${part}`,status:'reserved',encrypted_tokens:cipher});
  }
  const cancelTail=j=>{for(const x of jobs)if(x.owner_id===j.owner_id&&x.status==='reserved')x.status='cancelled';};
  const eligible=j=>j.status==='reserved'&&!jobs.some(x=>x.owner_id===j.owner_id&&x.status==='sending');
  const fetcher=async(url,init)=>{
   if(url==='https://kapi.kakao.com/v2/api/talk/memo/default/send') {
    assert.ok(now<start+600000,'Never initiate a send after the validated deadline');
    now+=sendMs;
    const body=JSON.parse(new URLSearchParams(init.body).get('template_object')).text;
    const j=jobs.find(x=>x.body===body);assert.ok(j);assert.equal(j.status,'sending');
    assert.equal(init.headers.Authorization,'Bearer '+j.owner_id);
    attempts.push(j.id);
    if(j.id===uncertainId)throw Error('Synthetic lost provider response');
    return Response.json({result_code:0});
   }
   assert.ok(url.startsWith(env.SUPABASE_URL+'/rest/v1/rpc/'),'No external requests');
   now+=rpcMs;const name=url.split('/').at(-1),args=JSON.parse(init.body||'{}');
   let result=true;
   switch(name){
    case 'kakao_service_consume_tick':break;
    case 'kakao_service_gate':result={enabled:true};break;
    case 'kakao_service_tick_enter':units++;break;
    case 'kakao_service_expire':if(now>=start+600000)for(const j of jobs)if(j.status==='reserved')j.status='cancelled';break;
    case 'kakao_service_due':result=[];break; // Already reserved: isolates dispatch capacity.
    case 'kakao_service_pending':result=now<start+600000?jobs.filter(eligible).slice(0,args.p_limit).map(j=>({id:j.id})):[];break;
    case 'kakao_service_claim':{
     const j=jobs.find(x=>x.id===args.p_job_id);
     if(!eligible(j)||now>=start+600000||jobs.some(x=>x.owner_id===j.owner_id&&x.part<j.part&&x.status!=='accepted')){result={};break;}
     j.status='sending';claimed.push(j.id);result={...j,job_id:j.id,generation:1,claim_token:'synthetic-claim'};break;
    }
    case 'kakao_service_validate_claim':result=now<start+600000;break;
    case 'kakao_service_complete':{
     const j=jobs.find(x=>x.id===args.p_job_id);
     if(j.id===completionLostId&&args.p_status==='accepted')throw Error('Synthetic database response loss');
     j.status=args.p_status;
     if(j.status!=='accepted'||now>=start+600000)cancelTail(j);
     break;
    }
    case 'kakao_service_continue':continued=args.p_progress&&now<start+600000&&jobs.some(eligible);result=continued;break;
    default:throw Error('Unexpected RPC '+name);
   }
   return Response.json(result);
  };
  const worker=makeWorker(n=>env[n],fetcher);
  do {
   continued=false;ticks++;
   assert.ok(ticks<100,'Continuation must terminate');
   const response=await worker(new Request(env.SUPABASE_URL+'/tick',{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})}));
   assert.equal(response.status,200);
  }while(continued);
  assert.equal(new Set(attempts).size,attempts.length,'Never resend an attempted part');
  for(const id of attempts){const j=jobs.find(x=>x.id===id);const previous=partsByOwner.get(j.owner_id)||0;assert.equal(j.part,previous+1,'Strict per-owner part sequence');partsByOwner.set(j.owner_id,j.part);}
  return {jobs,attempts,claimed,ticks,units,elapsedMs:now-start};
 }finally{Date.now=originalNow;}
}

test('offline load: 20 owners x 5 parts drain in four bounded ticks without duplicates',async(t)=>{
 const r=await simulate();t.diagnostic(JSON.stringify({ticks:r.ticks,attempts:r.attempts.length,elapsedMs:r.elapsedMs,internalUnits:r.units}));assert.equal(r.attempts.length,100);assert.equal(r.ticks,4);assert.equal(r.units,104);assert.ok(r.jobs.every(j=>j.status==='accepted'));
});
test('offline slow load: continuation respects 10-minute cutoff instead of promising all 100 parts',async(t)=>{
 const r=await simulate({rpcMs:200,sendMs:9500});t.diagnostic(JSON.stringify({ticks:r.ticks,attempts:r.attempts.length,elapsedMs:r.elapsedMs,internalUnits:r.units}));assert.ok(r.ticks>4);assert.ok(r.attempts.length>0&&r.attempts.length<100);assert.ok(r.elapsedMs<620000);assert.ok(r.jobs.some(j=>j.status!=='accepted'));
});
test('offline partial failure: provider uncertainty stops owner tail, others drain without retry',async()=>{
 const r=await simulate({uncertainId:'owner-0-3'});assert.equal(r.attempts.length,98);assert.equal(r.jobs.find(j=>j.id==='owner-0-3').status,'uncertain');assert.equal(r.jobs.find(j=>j.id==='owner-0-4').status,'cancelled');assert.ok(r.jobs.filter(j=>j.owner_id!=='owner-0').every(j=>j.status==='accepted'));
});
test('offline database response loss after acceptance never resends the message',async()=>{
 const r=await simulate({completionLostId:'owner-0-3'});assert.equal(r.attempts.length,98);assert.equal(r.jobs.find(j=>j.id==='owner-0-3').status,'uncertain');assert.equal(r.attempts.filter(id=>id==='owner-0-3').length,1);
});
