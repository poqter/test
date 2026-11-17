import test from 'node:test';import assert from 'node:assert/strict';
import {makeTestWorker} from '../supabase/functions/hwarang-kakao-test/worker.mjs';import {seal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
async function run({expired=false,rotate=true,valid=true,uncertain=false,duplicate=false,body='테스트 일정 · '+ '가'.repeat(180)}={}){
const env={SUPABASE_URL:'https://local.invalid',SUPABASE_SERVICE_ROLE_KEY:'fake',KAKAO_MULTI_TOKEN_KEY:'x'.repeat(32),KAKAO_MULTI_ENABLED:'true',KAKAO_REST_API_KEY:'fake',KAKAO_CLIENT_SECRET:'fake'};
let sends=0,refreshes=0;const calls=[];const cipher=await seal({access_token:'fake',refresh_token:'fake',expires_at:Date.now()+(expired?-1000:900000),refresh_expires_at:Date.now()+9000000},env.KAKAO_MULTI_TOKEN_KEY,'owner',1);
const worker=makeTestWorker(n=>env[n],async(u,i)=>{
calls.push(u.split('/').at(-1));
if(u.endsWith('kakao_test_claim'))return Response.json(duplicate?null:{id:'r',owner_id:'owner',generation:1,claim_token:'c',day:'2026-11-17',sample_body:body,encrypted_tokens:cipher,summary:{events:[{title:'실제 일정은 보내지 않음',id:'x'}],preferences:{weather_region_key:'seoul'}}});
if(u.endsWith('/oauth/token')){refreshes++;return Response.json({access_token:'renewed-fake',expires_in:3600});}
if(u.endsWith('kakao_service_rotate'))return Response.json(rotate);
if(u.endsWith('kakao_test_validate'))return Response.json(valid);
if(u.endsWith('kakao_test_complete'))return Response.json(true);
if(u.endsWith('/memo/default/send')){sends++;assert.equal(JSON.parse(i.body.get('template_object')).text,body);if(uncertain)throw Error('timeout');return Response.json({result_code:0});}
throw Error('Forbidden path '+u);
});const r=await worker(new Request('https://local.invalid',{method:'POST',body:JSON.stringify({ticket:'a'.repeat(64)})}));return {sends,refreshes,calls,status:r.status};}
test('sample sends exact body once without weather or real schedule changes',async()=>{const r=await run();assert.equal(r.sends,1);assert.equal(r.status,200);assert(!r.calls.some(x=>/weather|reserve|continue/.test(x)));});
test('expired access safely refreshed and compare-and-swap saved before sending',async()=>{const r=await run({expired:true});assert.equal(r.sends,1);assert.equal(r.refreshes,1);assert.equal(r.calls.filter(x=>x==='kakao_test_validate').length,2);});
test('concurrent token change or revoked authorization cannot send',async()=>{for(const opts of [{expired:true,rotate:false},{expired:true,valid:false}])assert.equal((await run(opts)).sends,0);});
test('duplicate ticket, oversized UTF16 and blank sample cannot send',async()=>{for(const opts of [{duplicate:true},{body:'😀'.repeat(101)},{body:'   '}])assert.equal((await run(opts)).sends,0);});
test('ambiguous response never retried',async()=>{const r=await run({uncertain:true});assert.equal(r.sends,1);assert.equal(r.status,503);});
