import {briefingBundle} from './message.mjs';
import {forecastBase} from './weather.mjs';
import {fetchWebWeather} from './weather-web.mjs';
import {unseal,seal,digest} from './crypto.mjs';
import {refreshToken,sendMemo,template,ReauthenticationRequired} from './kakao-api.mjs';
/** Server-only bounded worker. Remains OFF until transactional RPCs pass integration review. */
export function makeWorker(env,fetcher=fetch) {
 const base=env('SUPABASE_URL'),service=env('SUPABASE_SERVICE_ROLE_KEY');
 const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 async function db(path,body,method='POST') {
  const r=await fetcher(base+'/rest/v1/'+path,{method,headers:{apikey:service,Authorization:'Bearer '+service,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000),redirect:'error'});
  if(!r.ok)throw Error('Storage unavailable');return r.json();
 }
 const rpc=(name,body={})=>db('rpc/'+name,body);
 return async req=>{
  if(req.method!=='POST')return response({error:'Method not allowed'},405);
  if(env('KAKAO_MULTI_ENABLED')!=='true')return response({error:'Disabled'},503);

  let processed=0,progress=false;const tickStarted=Date.now();
  try {
   if(Number(req.headers.get('content-length')||0)>256)return response({error:'Unauthorized'},401);
   const raw=await req.text();if(raw.length>256)return response({error:'Unauthorized'},401);
   let input;try{input=JSON.parse(raw);}catch{return response({error:'Unauthorized'},401);}
   if(!/^[a-f0-9]{64}$/.test(input?.ticket||''))return response({error:'Unauthorized'},401);
   const tickHash=await digest(input.ticket);
   if(!(await rpc('kakao_service_consume_tick',{p_ticket_hash:tickHash})))return response({error:'Unauthorized'},401);
   if(!env('KAKAO_MULTI_TOKEN_KEY'))throw Error('Key missing');
   const gate=await rpc('kakao_service_gate');if(!gate?.enabled)return response({held:true});
   const tick=crypto.randomUUID();
   if(!(await rpc('kakao_service_tick_enter',{p_run_id:tick})))return response({held:true});
   await rpc('kakao_service_expire');
   const due=await rpc('kakao_service_due',{p_run_id:tick,p_limit:25});
   const weatherMemo=new Map();
   async function weatherFor(item){
    const region=item.summary?.preferences?.weather_region_key;
    if(!region)return {status:'unavailable'};
    const key=region+':'+item.day;
    if(!weatherMemo.has(key))weatherMemo.set(key,(async()=>{
     let claim,args;
     try{
      const baseIssue=forecastBase();
      args={p_region_key:region,p_forecast_day:item.day,p_base_date:baseIssue.base_date,p_base_time:baseIssue.base_time};
      claim=await rpc('kakao_service_weather_claim',args);
      if(claim?.status==='cached')return {...claim.forecast,region_name:claim.region_name};
      if(claim?.status!=='fetch'||!claim.lease_token)return {status:'unavailable',region_name:claim?.region_name};
      const forecast=await fetchWebWeather(fetcher,{day:item.day,forecast_code:claim.forecast_code});
      const stored=await rpc('kakao_service_weather_complete',{...args,p_lease_token:claim.lease_token,p_forecast:forecast});
      if(stored!==true)throw Error('Weather changed');
      return {...forecast,region_name:claim.region_name};
     }catch{
      if(claim?.lease_token&&args)await rpc('kakao_service_weather_complete',{...args,p_lease_token:claim.lease_token,p_forecast:null}).catch(()=>{});
      return {status:'unavailable',region_name:claim?.region_name};
     }
    })());
    return weatherMemo.get(key);
   }
   for(const item of due.slice(0,25)) {
    if(Date.now()-tickStarted>20000)break;
    const hasBranch=item.summary.identity?.position==='branch_manager'&&!!item.summary.branch;
    const skipEmpty=!hasBranch&&Array.isArray(item.summary.events)&&item.summary.events.length===0&&item.summary.preferences?.send_empty===false;
    const weather=skipEmpty?{status:'unavailable'}:await weatherFor(item);
    const bundle=briefingBundle(item.day,item.summary,weather);
    const parts=bundle.map(p=>p.body);
    if(!parts.length||parts.some(p=>typeof p!=='string'||!p.trim()||p.length>200))throw Error('Invalid manifest');
    const args={p_owner:item.owner_id,p_day:item.day,p_generation:item.generation,p_parts:parts,p_scope_hash:item.scope_hash};
    const reserved=hasBranch
      ?await rpc('kakao_service_reserve_branch',{...args,p_branch_parts:bundle.filter(p=>p.kind==='branch').length})
      :await rpc('kakao_service_reserve',args);
    if(reserved?.batch_id)progress=true;
   }
   const pending=await rpc('kakao_service_pending',{p_limit:25});
   // The new pending contract adds owner/part. Old DB deployments fall back to serial.
   const items=pending.slice(0,25);
   const grouped=items.every(j=>typeof j.owner_id==='string'&&j.owner_id&&Number.isInteger(j.part)&&j.part>0);
   const groups=[];
   if(grouped){
    const byOwner=new Map();
    for(const item of items){if(!byOwner.has(item.owner_id)){const group={owner:item.owner_id,jobs:[]};byOwner.set(item.owner_id,group);groups.push(group);}byOwner.get(item.owner_id).jobs.push(item);}
    // Keep DB chronology inside each owner: midnight can expose two different batches.
   }else if(items.length)groups.push({owner:null,jobs:items});
   let stopped=false,storageFailed=false,nextGroup=0;
   async function deliver(pendingJob,expectedOwner){
    if(stopped||Date.now()-tickStarted>40000)return false;
    let job;
    if(pendingJob.atomic_claim===true){
     job=await rpc('kakao_service_begin_job',{p_job_id:pendingJob.id});
     if(job?.reason==='quota_held')stopped=true;
    }else{
     const run=crypto.randomUUID();
     if(!(await rpc('kakao_service_tick_enter',{p_run_id:run}))){stopped=true;return false;}
     job=await rpc('kakao_service_claim',{p_job_id:pendingJob.id,p_run_id:run});
    }
    if(!job?.claim_token)return false;
    if(expectedOwner!==null&&job.owner_id!==expectedOwner){
     await rpc('kakao_service_complete',{p_job_id:job.job_id,p_claim_token:job.claim_token,p_status:'failed'}).catch(()=>{});
     return false;
    }
    progress=true;
    let attempted=false;
    try {
     let token=await unseal(job.encrypted_tokens,env('KAKAO_MULTI_TOKEN_KEY'),job.owner_id,job.generation);
     if(!Number.isFinite(token.refresh_expires_at)||token.refresh_expires_at<=Date.now())throw new ReauthenticationRequired();
     if(token.expires_at<=Date.now()+300000){
      token=await refreshToken(fetcher,{clientId:env('KAKAO_REST_API_KEY'),clientSecret:env('KAKAO_CLIENT_SECRET')},token);
      const cipher=await seal(token,env('KAKAO_MULTI_TOKEN_KEY'),job.owner_id,job.generation);
      const saved=await rpc('kakao_service_rotate',{p_owner:job.owner_id,p_generation:job.generation,p_previous_cipher:job.encrypted_tokens,p_new_cipher:cipher});
      if(!saved)throw Error('Token changed');
     }
     // This second atomic authorization check is required after potential refresh latency.
     if(!(await rpc('kakao_service_validate_claim',{p_job_id:job.job_id,p_claim_token:job.claim_token})))throw Error('Authorization changed');
     attempted=true;
     const kind=job.message_kind==='branch'?'branch':'personal';
     await sendMemo(fetcher,token.access_token,template(job.body,'https://hwarang-calendar.streamlit.app/calendar?view=mobile-calendar&calendar_briefing='+kind,kind));
     const recorded=await rpc('kakao_service_complete',{p_job_id:job.job_id,p_claim_token:job.claim_token,p_status:'accepted'});
     if(recorded!==true)throw Error('Acceptance not persisted');
     processed++;return true;
    } catch (error) {
     const reauth=error instanceof ReauthenticationRequired;
     // Definite provider rejection is not an ambiguous accepted request.
     if(reauth)await rpc('kakao_service_require_reauth',{p_owner:job.owner_id,p_generation:job.generation}).catch(()=>{});
     await rpc('kakao_service_complete',{p_job_id:job.job_id,p_claim_token:job.claim_token,p_status:attempted&&!reauth?'uncertain':'failed'}).catch(()=>{});
     return false;
    }
   }
   async function lane(){
    while(!stopped&&Date.now()-tickStarted<=40000){
     const group=groups[nextGroup++];if(!group)return;
     for(const item of group.jobs){
      if(stopped||Date.now()-tickStarted>40000)break;
      try{
       const accepted=await deliver(item,group.owner);
       // A refused/failed/uncertain part closes this owner's local stale queue.
       // SQL remains authoritative across concurrent Edge invocations.
       if(!accepted&&group.owner!==null)break;
      }catch{storageFailed=true;stopped=true;break;}
     }
    }
   }
   // Await every lane, including in-flight sends on another owner's failure.
   await Promise.all(Array.from({length:Math.min(grouped?3:1,groups.length)},()=>lane()));
   if(storageFailed)return response({error:'Worker unavailable',processed},503);
   await rpc('kakao_service_continue',{p_tick_hash:tickHash,p_progress:progress});
   return response({processed});
  }catch{return response({error:'Worker unavailable',processed},503);}
 };
}
