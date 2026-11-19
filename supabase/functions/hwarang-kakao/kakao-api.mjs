// Provider-independent core. Only definite consent/refresh expiry errors require reconnect.
export class ReauthenticationRequired extends Error { constructor(){super('Reauthentication required');this.name='ReauthenticationRequired';} }
export const MEMO_ENDPOINT='https://kapi.kakao.com/v2/api/talk/memo/default/send';
export const TOKEN_ENDPOINT='https://kauth.kakao.com/oauth/token';
export function template(text, calendarUrl, kind='personal') {
 const url=new URL(calendarUrl);
 if(url.protocol!=='https:' || url.hostname!=='hwarang-calendar.streamlit.app' || url.username || url.password) throw new Error('Invalid calendar URL');
 if(typeof text!=='string'||!text.trim()||text.length>200) throw new Error('Text must contain 1–200 UTF-16 units');
 return {object_type:'text',text,link:{web_url:url.href,mobile_web_url:url.href},button_title:kind==='branch'?'오늘 지점 일정 보기':'내 일정 보기'};
}
export function mergeTokens(previous, response, now=Date.now()) {
 if(typeof response.access_token!=='string'||!response.access_token || !Number.isFinite(response.expires_in)||response.expires_in<=0) throw new Error('Invalid token response');
 const next={...previous,access_token:response.access_token,expires_at:now+response.expires_in*1000};
 if(response.refresh_token) {
  if(!Number.isFinite(response.refresh_token_expires_in)||response.refresh_token_expires_in<=0) throw new Error('Invalid refresh lifetime');
  next.refresh_token=response.refresh_token;next.refresh_expires_at=now+response.refresh_token_expires_in*1000;
 }
 return next;
}
export async function refreshToken(fetcher, config, previous, now=Date.now()) {
 if(!config.clientId||!config.clientSecret||!previous.refresh_token) throw new Error('Connection setup required');
 const res=await fetcher(TOKEN_ENDPOINT,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'refresh_token',client_id:config.clientId,client_secret:config.clientSecret,refresh_token:previous.refresh_token}),signal:AbortSignal.timeout(10000),redirect:'error'});
 if(!res.ok) {
  const error=await res.json().catch(()=>({}));
  if(error.error==='invalid_grant'&&error.error_code==='KOE322')throw new ReauthenticationRequired();
  throw new Error('Token refresh failed');
 }
 return mergeTokens(previous,await res.json(),now);
}
export async function sendMemo(fetcher, accessToken, message) {
 if(!accessToken) throw new Error('Connection setup required');
 // No retry: timeout may mean an accepted message with a lost response.
 const res=await fetcher(MEMO_ENDPOINT,{method:'POST',headers:{Authorization:`Bearer ${accessToken}`,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({template_object:JSON.stringify(message)}),signal:AbortSignal.timeout(10000),redirect:'error'});
 if(!res.ok) {
  const error=await res.json().catch(()=>({}));
  if(error.code===-402||error.code===-101)throw new ReauthenticationRequired();
  throw new Error('Kakao did not confirm acceptance');
 }
 const result=await res.json();
 if(result.result_code!==0) throw new Error('Kakao did not confirm acceptance');
 return {accepted:true}; // Not proof of device delivery/read.
}
export function privateEventSummary(e,owner) {
 const own=e.owner===owner;
 if(!own&&!e.common&&e.companion!==owner) throw new Error('Out of scope');
 return {day:e.day,start_time:e.start_time,title:e.title,status:e.status,kind:e.kind,time_pending:e.time_pending,...(own?{end_time:e.end_time,place:e.place}:{})};
}
