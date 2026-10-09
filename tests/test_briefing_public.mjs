import nodeAssert from 'node:assert/strict';
let assertions=0;const assert=new Proxy(nodeAssert,{get:(target,key)=>typeof target[key]==='function'?((...args)=>{assertions++;return target[key](...args);}):target[key]});
import { handle } from '../public_reader/worker.js';
const token='x'.repeat(43), key='synthetic-service-key';
const url='https://example.org/functions/v1/briefing-public?token='+token;
const packet={schema:'hwarang-share-v3',asset_version:'a'.repeat(24),rendered_html:'<!doctype html><meta property="og:title" content="등록 이름 팀장"><h1>종합뉴스</h1><p>로그인 없이 읽기</p>'};
const env=n=>n==='SUPABASE_URL'?'https://example.org':n==='SUPABASE_SERVICE_ROLE_KEY'?key:undefined;
let calls=[];
const deps={env,fetcher:async(u,o)=>{calls.push([u,o]);return new Response(JSON.stringify(packet),{headers:{'Content-Type':'application/json'}});}};
let r=await handle(new Request(url),deps);assert.equal(r.status,200);let html=await r.text();assert.ok(html.includes('og:title')&&html.includes('등록 이름 팀장'));assert.ok(!html.includes(key));assert.equal(calls.length,1);assert.ok(calls[0][0].endsWith('hwarang_read_public_briefing'));
assert.equal(r.headers.get('Cache-Control'),'private, no-store, max-age=0');
for(const suffix of ['','&asset=pdf','&asset=preview']){
  calls=[];r=await handle(new Request(url+suffix),{env,fetcher:async(u,o)=>{calls.push(u);return new Response('null');}});
  assert.equal(r.status,410);assert.equal(calls.length,1);assert.ok(!(await r.text()).includes('등록 이름'));
}
for(const [asset,mime] of [['preview','image/png'],['pdf','application/pdf']]){
 calls=[];r=await handle(new Request(url+'&asset='+asset),{env,fetcher:async(u,o)=>{calls.push([u,o]);return u.includes('/rpc/')?new Response(JSON.stringify(packet)):new Response(new Uint8Array([1,2,3]),{headers:{'Content-Type':mime}});}});
 assert.equal(r.status,200);assert.equal(r.headers.get('Content-Type'),mime);assert.equal(calls.length,2);assert.ok(calls[1][0].includes('/'+token+'/'+packet.asset_version+'/'));assert.equal(calls[1][1].headers.Authorization,'Bearer '+key);
}
r=await handle(new Request(url+'&asset=evil'),deps);assert.equal(r.status,404);
r=await handle(new Request(url,{method:'POST'}),deps);assert.equal(r.status,405);
r=await handle(new Request(url),{env,fetcher:async()=>new Response('secret error',{status:403})});assert.equal(r.status,503);assert.ok(!(await r.text()).includes('secret error'));
r=await handle(new Request(url),{env,fetcher:async()=>{throw new Error('secret');}});assert.equal(r.status,503);
r=await handle(new Request(url+'&asset=pdf'),{env,fetcher:async u=>u.includes('/rpc/')?new Response(JSON.stringify(packet)):new Response('wrong type',{headers:{'Content-Type':'text/html'}})});assert.equal(r.status,503);
r=await handle(new Request('https://example.org/?health=1'),{env,fetcher:async()=>{throw new Error('Health called DB');}});assert.equal(r.status,200);assert.equal((await r.json()).schema,'hwarang-share-v3');
r=await handle(new Request(url,{method:'HEAD'}),deps);assert.equal(r.status,200);assert.equal(await r.text(),'');
r=await handle(new Request('https://example.org/?health=1'),{env:()=>undefined,fetcher:async()=>{throw new Error('Health called DB');}});assert.equal(r.status,503);
calls=[];r=await handle(new Request(url),{env:n=>n==='SUPABASE_SERVICE_ROLE_KEY'?'sb_secret_synthetic':env(n),fetcher:async(u,o)=>{calls.push(o);return new Response(JSON.stringify(packet));}});assert.equal(r.status,200);assert.equal(calls[0].headers.apikey,'sb_secret_synthetic');assert.ok(!('Authorization' in calls[0].headers));
console.log('Customer HTTP: '+assertions+' assertions passed (HTML, OG, anonymous reads, assets, live closure, no secrets).');
