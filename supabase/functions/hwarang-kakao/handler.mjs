import {random,digest,seal} from './crypto.mjs';
export function makeHandler(env,fetcher=fetch) {
 const base=env('SUPABASE_URL'),service=env('SUPABASE_SERVICE_ROLE_KEY'),client=env('KAKAO_REST_API_KEY'),secret=env('KAKAO_CLIENT_SECRET'),encryption=env('KAKAO_MULTI_TOKEN_KEY');
 const callback=base+'/functions/v1/hwarang-kakao/callback';
 const reply=(body,status=200,headers={})=>new Response(typeof body==='string'?body:JSON.stringify(body),{status,headers:{'Content-Type':typeof body==='string'?'text/plain; charset=utf-8':'application/json','Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',...headers}});
 async function request(path,method='POST',body,token=service) {
  const r=await fetcher(base+path,{method,headers:{apikey:service,Authorization:'Bearer '+token,'Content-Type':'application/json',Prefer:'return=representation'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000),redirect:'error'});
  if(!r.ok)throw Error('Operation failed');return r.json();
 }
 return async req=>{
  try {
   const url=new URL(req.url),path=url.pathname.split('/').pop();
   // Deployment is inert until costs, schema and OAuth domain registration are verified.
   if(env('KAKAO_MULTI_ENABLED')!=='true')return reply({error:'현재 준비 중입니다.'},503);
   if(!base||!service||!client||!secret||!encryption)return reply({error:'연결 설정을 확인해 주세요.'},503);
   if(path==='connect'&&req.method==='POST') {
    const bearer=req.headers.get('authorization')?.match(/^Bearer (\S+)$/)?.[1];
    if(!bearer||bearer===service)return reply({error:'로그인이 필요합니다.'},401);
    const user=await request('/auth/v1/user','GET',undefined,bearer);
    if(!user.id)return reply({error:'로그인이 필요합니다.'},401);
    // RPC verifies live auth.sessions, active profile and current workspace permissions.
    await request('/rest/v1/rpc/kakao_my_status','POST',{},bearer);
    const ticket=random();
    await request('/rest/v1/rpc/kakao_service_begin','POST',{p_owner:user.id,p_ticket_hash:await digest(ticket)});
    return reply({url:base+'/functions/v1/hwarang-kakao/start?ticket='+ticket});
   }
   if(req.method!=='GET')return reply({error:'Method not allowed'},405);
   if(path==='start') {
    const ticket=url.searchParams.get('ticket');if(!/^[a-f0-9]{64}$/.test(ticket||''))return reply('연결 링크가 유효하지 않습니다.',403);
    const state=random(),browser=random();
    const rows=await request('/rest/v1/kakao_multi_oauth?ticket_hash=eq.'+await digest(ticket)+'&status=eq.invited&expires_at=gt.'+encodeURIComponent(new Date().toISOString()),'PATCH',{state_hash:await digest(state),browser_hash:await digest(browser),status:'started'});
    if(rows.length!==1)return reply('연결 링크가 만료되었거나 사용되었습니다.',403);
    const to=new URL('https://kauth.kakao.com/oauth/authorize');to.search=new URLSearchParams({client_id:client,redirect_uri:callback,response_type:'code',scope:'talk_message',state}).toString();
    return reply('',302,{Location:to.href,'Set-Cookie':'hwarang_kakao='+browser+'; Max-Age=600; Path=/functions/v1/hwarang-kakao; HttpOnly; Secure; SameSite=Lax'});
   }
   if(path!=='callback')return reply('Not found',404);
   const state=url.searchParams.get('state'),code=url.searchParams.get('code');
   const browser=(req.headers.get('cookie')||'').match(/(?:^|;\s*)hwarang_kakao=([a-f0-9]{64})(?:;|$)/)?.[1];
   if(!/^[a-f0-9]{64}$/.test(state||'')||!browser||!code||code.length>4096)return reply('인증을 완료하지 못했습니다. 캘린더에서 다시 연결하세요.',400);
   const rows=await request('/rest/v1/kakao_multi_oauth?state_hash=eq.'+await digest(state)+'&browser_hash=eq.'+await digest(browser)+'&status=eq.started&expires_at=gt.'+encodeURIComponent(new Date().toISOString()),'PATCH',{status:'exchanging'});
   if(rows.length!==1)return reply('인증이 만료되었거나 사용되었습니다.',400);
   const row=rows[0];
   const tokenResponse=await fetcher('https://kauth.kakao.com/oauth/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:client,client_secret:secret,redirect_uri:callback,code}),signal:AbortSignal.timeout(10000),redirect:'error'});
   if(!tokenResponse.ok)throw Error('Exchange failed');const token=await tokenResponse.json();
   if(!token.access_token||!token.refresh_token||!Number.isFinite(token.expires_in)||token.expires_in<=0||!Number.isFinite(token.refresh_token_expires_in)||token.refresh_token_expires_in<=0||!String(token.scope||'').split(' ').includes('talk_message'))throw Error('Consent missing');
   const info=await fetcher('https://kapi.kakao.com/v1/user/access_token_info',{headers:{Authorization:'Bearer '+token.access_token},signal:AbortSignal.timeout(10000),redirect:'error'});
   if(!info.ok)throw Error('Identity failed');const account=await info.json();
   if(account.app_id!==Number(env('KAKAO_APP_ID'))||!Number.isSafeInteger(account.id)||account.id<=0)throw Error('App mismatch');
   const now=Date.now(),encrypted=await seal({access_token:token.access_token,refresh_token:token.refresh_token,expires_at:now+token.expires_in*1000,refresh_expires_at:now+token.refresh_token_expires_in*1000},encryption,row.owner_id,row.generation);
   const receipt=random();
   await request('/rest/v1/rpc/kakao_service_finish','POST',{p_ticket_id:row.id,p_generation:row.generation,p_account_id:String(account.id),p_encrypted_tokens:encrypted,p_receipt_hash:await digest(receipt)});
   return reply('아직 연결이 확정되지 않았습니다. 본인이 로그인한 화랑 캘린더의 카카오 설정에서 아래 확인 코드를 입력하세요. 다른 사람에게 코드를 보내지 마세요. 본인이 연결을 시작하지 않았다면 창을 닫으세요. 코드는 10분 후 만료됩니다.\n\n'+receipt,200,{'Set-Cookie':'hwarang_kakao=; Max-Age=0; Path=/functions/v1/hwarang-kakao; HttpOnly; Secure; SameSite=Lax'});
  } catch {return reply({error:'처리하지 못했습니다. 캘린더에서 상태를 확인하고 다시 시도하세요.'},503);}
 };
}
