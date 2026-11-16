import {briefing} from './message.mjs';
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
   for(const item of due.slice(0,25)) {
    if(Date.now()-tickStarted>20000)break;
    const parts=briefing(item.day,item.summary.events,item.summary.empty_explicit);
    if(!parts.length||parts.some(p=>typeof p!=='string'||!p.trim()||p.length>200))throw Error('Invalid manifest');
    const reserved=await rpc('kakao_service_reserve',{p_owner:item.owner_id,p_day:item.day,p_generation:item.generation,p_parts:parts,p_scope_hash:item.scope_hash});
    if(reserved?.batch_id)progress=true;
   }
   const pending=await rpc('kakao_service_pending',{p_limit:25});
   for(const pendingJob of pending.slice(0,25)) {
    if(Date.now()-tickStarted>40000)break;
    const run=crypto.randomUUID();if(!(await rpc('kakao_service_tick_enter',{p_run_id:run})))break;
    const job=await rpc('kakao_service_claim',{p_job_id:pendingJob.id,p_run_id:run});
    if(!job?.claim_token)continue;
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
     await sendMemo(fetcher,token.access_token,template(job.body,'https://hwarang-calendar.streamlit.app/calendar?view=mobile-calendar'));
     const recorded=await rpc('kakao_service_complete',{p_job_id:job.job_id,p_claim_token:job.claim_token,p_status:'accepted'});
     if(recorded!==true)throw Error('Acceptance not persisted');
     processed++;
    } catch (error) {
     const reauth=error instanceof ReauthenticationRequired;
     // Definite provider rejection is not an ambiguous accepted request.
     if(reauth)await rpc('kakao_service_require_reauth',{p_owner:job.owner_id,p_generation:job.generation}).catch(()=>{});
     await rpc('kakao_service_complete',{p_job_id:job.job_id,p_claim_token:job.claim_token,p_status:attempted&&!reauth?'uncertain':'failed'}).catch(()=>{});
    }
   }
   await rpc('kakao_service_continue',{p_tick_hash:tickHash,p_progress:progress});
   return response({processed});
  }catch{return response({error:'Worker unavailable',processed},503);}
 };
}
