import {digest,unseal,seal} from '../hwarang-kakao/crypto.mjs';
import {briefing} from '../hwarang-kakao/message.mjs';
import {forecastBase} from '../hwarang-kakao/weather.mjs';
import {fetchWebWeather} from '../hwarang-kakao/weather-web.mjs';
import {sendMemo,template,refreshToken,ReauthenticationRequired} from '../hwarang-kakao/kakao-api.mjs';
/** One explicit self-test, one message maximum. Never changes a daily batch or schedule. */
export function makeTestWorker(env,fetcher=fetch) {
 const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 const base=env('SUPABASE_URL'),key=env('SUPABASE_SERVICE_ROLE_KEY');
 async function rpc(name,body={}) {
  const r=await fetcher(base+'/rest/v1/rpc/'+name,{method:'POST',headers:{apikey:key,Authorization:'Bearer '+key,'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(10000),redirect:'error'});
  if(!r.ok)throw Error('Storage failed');return r.json();
 }
 return async request=>{
  if(request.method!=='POST')return reply({error:'Method not allowed'},405);
  if(env('KAKAO_MULTI_ENABLED')!=='true')return reply({error:'Disabled'},503);
  let job,attempted=false;
  try {
   if(Number(request.headers.get('content-length')||0)>256)return reply({error:'Unauthorized'},401);
   const raw=await request.text();if(raw.length>256)return reply({error:'Unauthorized'},401);
   let input;try{input=JSON.parse(raw);}catch{return reply({error:'Unauthorized'},401);}
   if(!/^[a-f0-9]{64}$/.test(input?.ticket||''))return reply({error:'Unauthorized'},401);
   job=await rpc('kakao_test_claim',{p_ticket_hash:await digest(input.ticket)});
   if(!job?.claim_token)return reply({error:'Unavailable or already used'},409);
   let token=await unseal(job.encrypted_tokens,env('KAKAO_MULTI_TOKEN_KEY'),job.owner_id,job.generation);
   if(!Number.isFinite(token.refresh_expires_at)||token.refresh_expires_at<=Date.now())throw new ReauthenticationRequired();
   if(!Number.isFinite(token.expires_at)||token.expires_at<=Date.now()+300000){
    if(await rpc('kakao_test_validate',{p_id:job.id,p_claim_token:job.claim_token})!==true)throw Error('Authorization changed');
    token=await refreshToken(fetcher,{clientId:env('KAKAO_REST_API_KEY'),clientSecret:env('KAKAO_CLIENT_SECRET')},token);
    const cipher=await seal(token,env('KAKAO_MULTI_TOKEN_KEY'),job.owner_id,job.generation);
    if(await rpc('kakao_service_rotate',{p_owner:job.owner_id,p_generation:job.generation,p_previous_cipher:job.encrypted_tokens,p_new_cipher:cipher})!==true)throw Error('Token changed');
   }
   if(job.sample_body!=null&&(typeof job.sample_body!=='string'||!job.sample_body.trim()||job.sample_body.length>200))throw Error('Invalid sample');
   const region=job.summary?.preferences?.weather_region_key;if(!region)throw Error('Region missing');
   let weather,args,claim;
   if(job.sample_body!=null){weather=undefined;
   }else if(job.cached_weather_only){
    if(job.cached_weather?.status!=='ok'||job.cached_weather.day!==job.day)throw Error('Fresh cached weather required');
    weather=job.cached_weather;
   }else try {
    const issue=forecastBase();args={p_region_key:region,p_forecast_day:job.day,p_base_date:issue.base_date,p_base_time:issue.base_time};
    claim=await rpc('kakao_test_weather_claim',{p_id:job.id,p_claim_token:job.claim_token,p_base_date:issue.base_date,p_base_time:issue.base_time});
    if(claim?.status==='cached')weather={...claim.forecast,region_name:claim.region_name};
    else if(claim?.status==='fetch'&&claim.lease_token){
     const result=await fetchWebWeather(fetcher,{day:job.day,forecast_code:claim.forecast_code});
     if(await rpc('kakao_service_weather_complete',{...args,p_lease_token:claim.lease_token,p_forecast:result})!==true)throw Error('Weather storage failed');
     weather={...result,region_name:claim.region_name};
    }else weather={status:'unavailable',region_name:claim?.region_name};
   }catch{
    if(args&&claim?.lease_token)await rpc('kakao_service_weather_complete',{...args,p_lease_token:claim.lease_token,p_forecast:null}).catch(()=>{});
    weather={status:'unavailable',region_name:claim?.region_name};
   }
   const parts=briefing(job.day,job.summary.events,job.summary.empty_explicit,weather);
   const text=job.sample_body??parts.join('\n');
   if(text.length>200)throw Error('Test exceeds single message cap');
   if(await rpc('kakao_test_validate',{p_id:job.id,p_claim_token:job.claim_token})!==true)throw Error('Authorization changed');
   attempted=true;
   await sendMemo(fetcher,token.access_token,template(text,'https://hwarang-calendar.streamlit.app/calendar?view=mobile-calendar'));
   if(await rpc('kakao_test_complete',{p_id:job.id,p_claim_token:job.claim_token,p_status:'accepted'})!==true)throw Error('Acceptance unrecorded');
   return reply({accepted:true,length:text.length});
  }catch(error){
   const reason=error instanceof ReauthenticationRequired?'reconnect_required':['Authorization changed','Token changed','Invalid sample','Test exceeds single message cap'].includes(error?.message)?error.message:'preflight_failed';
   if(job?.claim_token)await rpc('kakao_test_complete',{p_id:job.id,p_claim_token:job.claim_token,p_status:attempted?'uncertain':'failed'}).catch(()=>{});
   return reply({error:attempted?'Outcome uncertain; do not retry':'Test not sent',reason:attempted?'uncertain':reason},503);
  }
 };
}
