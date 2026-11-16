import {digest,unseal} from '../hwarang-kakao/crypto.mjs';
import {briefing} from '../hwarang-kakao/message.mjs';
import {forecastBase} from '../hwarang-kakao/weather.mjs';
import {fetchWebWeather} from '../hwarang-kakao/weather-web.mjs';
import {sendMemo,template,ReauthenticationRequired} from '../hwarang-kakao/kakao-api.mjs';

/** First-onboarding delivery only. SQL owns eligibility, ledger, budgets and once-only tickets.
 * Continuation sends only unsent manifest parts; no provider retry or shared token rotation.
 */
export function makeWelcomeWorker(env,fetcher=fetch) {
 const base=env('SUPABASE_URL'),key=env('SUPABASE_SERVICE_ROLE_KEY');
 const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 async function rpc(name,body={}) {
  const response=await fetcher(base+'/rest/v1/rpc/'+name,{method:'POST',headers:{apikey:key,Authorization:'Bearer '+key,'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(10000),redirect:'error'});
  if(!response.ok)throw Error('Storage unavailable');return response.json();
 }
 async function weatherFor(job) {
  const region=job.summary?.preferences?.weather_region_key;
  if(!region)throw Error('Weather region missing');
  let claim,args;
  try {
   const issue=forecastBase();args={p_region_key:region,p_forecast_day:job.day,p_base_date:issue.base_date,p_base_time:issue.base_time};
   claim=await rpc('kakao_service_weather_claim',args);
   if(claim?.status==='cached')return {...claim.forecast,region_name:claim.region_name};
   if(claim?.status!=='fetch'||!claim.lease_token)return {status:'unavailable',region_name:claim?.region_name};
   const forecast=await fetchWebWeather(fetcher,{day:job.day,forecast_code:claim.forecast_code});
   if(await rpc('kakao_service_weather_complete',{...args,p_lease_token:claim.lease_token,p_forecast:forecast})!==true)throw Error('Weather storage changed');
   return {...forecast,region_name:claim.region_name};
  }catch{
   if(claim?.lease_token&&args)await rpc('kakao_service_weather_complete',{...args,p_lease_token:claim.lease_token,p_forecast:null}).catch(()=>{});
   return {status:'unavailable',region_name:claim?.region_name};
  }
 }
 return async request=>{
  if(request.method!=='POST')return reply({error:'Method not allowed'},405);
  if(env('KAKAO_MULTI_ENABLED')!=='true')return reply({error:'Disabled'},503);
  let job,part=null,attempted=false,acceptedParts=0;
  const started=Date.now();
  try {
   if(Number(request.headers.get('content-length')||0)>256)return reply({error:'Unauthorized'},401);
   const raw=await request.text();if(raw.length>256)return reply({error:'Unauthorized'},401);
   let input;try{input=JSON.parse(raw);}catch{return reply({error:'Unauthorized'},401);}
   if(!/^[a-f0-9]{64}$/.test(input?.ticket||''))return reply({error:'Unauthorized'},401);
   job=await rpc('kakao_welcome_claim',{p_ticket_hash:await digest(input.ticket)});
   if(!job?.claim_token)return reply({error:'Unavailable or already used'},409);
   const identity={p_id:job.id,p_claim_token:job.claim_token};
   const deadline=Date.parse(job.expires_at);
   const checkDeadline=()=>{if(!Number.isFinite(deadline)||Date.now()>=deadline)throw Error('Welcome deadline expired');};
   checkDeadline();
   const token=await unseal(job.encrypted_tokens,env('KAKAO_MULTI_TOKEN_KEY'),job.owner_id,job.generation);
   const checkToken=()=>{
    if(!Number.isFinite(token.expires_at)||token.expires_at<Date.now()+120000||!Number.isFinite(token.refresh_expires_at)||token.refresh_expires_at<=Date.now())throw new ReauthenticationRequired();
   };
   checkToken();
   let parts=job.parts;
   if(parts==null){
    const weather=await weatherFor(job);
    parts=briefing(job.day,job.summary.events,job.summary.empty_explicit,weather);
    if(!Array.isArray(parts)||!parts.length||parts.some(p=>typeof p!=='string'||!p.trim()||p.length>200))throw Error('Invalid manifest');
    const reservation=await rpc('kakao_welcome_reserve',{...identity,p_parts:parts});
    if(reservation?.reserved!==true)throw Error('Manifest not reserved');
   }
   if(!Array.isArray(parts)||!parts.length||parts.some(p=>typeof p!=='string'||!p.trim()||p.length>200))throw Error('Invalid manifest');
   const next=job.next_part??1;
   if(!Number.isInteger(next)||next<1||next>parts.length)throw Error('Invalid continuation');
   for(let n=next;n<=parts.length;n++) {
    checkDeadline();
    if(acceptedParts>=25||Date.now()-started>=40000) {
     // Exactly one enqueue attempt. A lost response must not cause a second ticket or cancellation.
     let queued;try{queued=await rpc('kakao_welcome_continue',identity);}catch{return reply({accepted_parts:acceptedParts,continuation:'unconfirmed'},503);}
     return reply({accepted_parts:acceptedParts,continuation:queued===true?'queued':'held'},queued===true?202:409);
    }
    checkToken();part=n;attempted=false;
    const claimed=await rpc('kakao_welcome_begin_part',{...identity,p_part:n});
    if(claimed?.claimed!==true||claimed.body!==parts[n-1])throw Error('Part unavailable or changed');
    if(await rpc('kakao_welcome_validate',identity)!==true)throw Error('Authorization changed');
    checkDeadline();checkToken();attempted=true;
    await sendMemo(fetcher,token.access_token,template(claimed.body,'https://hwarang-calendar.streamlit.app/calendar?view=mobile-calendar'));
    if(await rpc('kakao_welcome_complete_part',{...identity,p_part:n,p_status:'accepted'})!==true)throw Error('Acceptance unrecorded');
    acceptedParts++;part=null;attempted=false;
   }
   return reply({accepted:true,accepted_parts:acceptedParts}); // API acceptance, not device receipt.
  }catch(error){
   const reauth=error instanceof ReauthenticationRequired;
   if(job?.claim_token){
    const identity={p_id:job.id,p_claim_token:job.claim_token};
    if(part!==null)await rpc('kakao_welcome_complete_part',{...identity,p_part:part,p_status:attempted&&!reauth?'uncertain':'failed'}).catch(()=>{});
    await rpc('kakao_welcome_fail',{...identity,p_reason:reauth?'reauth_required':attempted?'outcome_uncertain':'setup_failed'}).catch(()=>{});
   }
   return reply({error:attempted&&!reauth?'Outcome uncertain; do not retry':reauth?'Reauthentication required':'Welcome stopped',accepted_parts:acceptedParts},503);
  }
 };
}
