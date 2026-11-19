import test from 'node:test';
import assert from 'node:assert/strict';
import {makeTestWorker} from '../supabase/functions/hwarang-kakao-test/worker.mjs';
import {briefingBundle} from '../supabase/functions/hwarang-kakao/message.mjs';
import {template} from '../supabase/functions/hwarang-kakao/kakao-api.mjs';
import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
const day='2026-11-20';
const weather={status:'ok',day,region_name:'서울',morning:'맑음',afternoon:'흐림',low:1,high:9,issued_day:day,issued_time:'05:00'};
function summary(position='team_leader',many=false){return {
 identity:{position},preferences:{weather_region_key:'seoul'},
 events:Array.from({length:many?24:1},(_,i)=>({id:String(i),title:'합성 개인 일정 '+i,start_time:'14:00'})),
 branch:{name:'합성 팀',members:Array.from({length:many?80:1},(_,i)=>({name:'합성직원'+i,count:0,state:'missing'}))}
};}
async function run(s,{failAt=0,revokeAt=0,complete=true,duplicate=false}={}){
 const config={SUPABASE_URL:'https://local.invalid',SUPABASE_SERVICE_ROLE_KEY:'fake',KAKAO_MULTI_ENABLED:'true',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32)};
 const cipher=await seal({access_token:'fake',refresh_token:'fake',expires_at:Date.now()+900000,refresh_expires_at:Date.now()+9000000},config.KAKAO_MULTI_TOKEN_KEY,'owner',1);
 const sent=[],completed=[],calls=[];let validations=0;
 const worker=makeTestWorker(n=>config[n],async(url,init)=>{
  const name=url.split('/').at(-1);calls.push(name);
  if(name==='kakao_test_claim')return Response.json(duplicate?null:{id:'test',owner_id:'owner',generation:1,claim_token:'claim',day,summary:s,encrypted_tokens:cipher,cached_weather_only:true,cached_weather:weather});
  if(name==='kakao_test_validate')return Response.json(++validations!==revokeAt);
  if(name==='kakao_test_complete'){completed.push(JSON.parse(init.body).p_status);return Response.json(complete);}
  if(url.endsWith('/memo/default/send')){sent.push(JSON.parse(init.body.get('template_object')));if(sent.length===failAt)throw Error('Lost response');return Response.json({result_code:0});}
  throw Error('Unexpected call '+name);
 });
 const response=await worker(new Request('https://local.invalid',{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})}));
 return {status:response.status,result:await response.json(),sent,completed,calls,validations};
}
for(const role of ['team_leader','deputy_branch_manager','branch_manager','fp'])test(role+' test matches every regular body, button and link in order',async()=>{
 const s=summary(role),r=await run(s);
 const expected=briefingBundle(day,s,weather).map(p=>template(p.body,'https://hwarang-calendar.streamlit.app/calendar?view=mobile-calendar&calendar_briefing='+p.kind,p.kind));
 assert.equal(r.status,200);assert.deepEqual(r.sent,expected);assert.equal(r.validations,expected.length);assert.deepEqual(r.completed,['accepted']);
 assert(!r.calls.some(c=>/reserve|enqueue|continue|due|save_preferences/.test(c)));
});
test('large staff list and personal schedules split exactly like regular, no missing or truncated names',async()=>{
 const s=summary('branch_manager',true),r=await run(s),expected=briefingBundle(day,s,weather);
 assert.equal(r.status,200);assert(r.sent.length>3);assert.deepEqual(r.sent.map(m=>m.text),expected.map(p=>p.body));
 assert(r.sent.every(m=>m.text.length<=200));
 for(const member of s.branch.members)assert(r.sent.some(m=>m.text.includes(member.name)));
});
test('member preference off and no linked members both send personal only',async()=>{
 for(const s of [{...summary(),branch:null},{...summary(),preferences:{weather_region_key:'seoul',member_briefing_enabled:false}}]){
  const r=await run(s);assert.equal(r.status,200);assert(r.sent.every(m=>m.button_title==='내 일정 보기'));
 }
});
test('ambiguous first or later part stops remainder and never marks accepted',async()=>{
 for(const failAt of [1,2]){const r=await run(summary('branch_manager',true),{failAt});assert.equal(r.sent.length,failAt);assert.equal(r.status,503);assert.deepEqual(r.completed,['uncertain']);assert.equal(r.result.accepted_parts,failAt-1);}
});
test('scope or consent change before first send fails; after a send marks partial uncertain',async()=>{
 for(const revokeAt of [1,2]){const r=await run(summary(),{revokeAt});assert.equal(r.sent.length,revokeAt-1);assert.equal(r.status,503);assert.deepEqual(r.completed,[revokeAt===1?'failed':'uncertain']);}
});
test('duplicate claim sends nothing and failed completion never retries messages',async()=>{
 const duplicate=await run(summary(),{duplicate:true});assert.equal(duplicate.status,409);assert.equal(duplicate.sent.length,0);
 const r=await run(summary(),{complete:false});assert.equal(r.status,503);assert.equal(r.sent.length,2);assert.deepEqual(r.completed,['accepted','uncertain']);
});
