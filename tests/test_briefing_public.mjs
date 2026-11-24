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
for(const suffix of ['']){
  calls=[];r=await handle(new Request(url+suffix),{env,fetcher:async(u,o)=>{calls.push(u);return new Response('null');}});
  assert.equal(r.status,410);assert.equal(calls.length,1);assert.ok(!(await r.text()).includes('등록 이름'));
}
for(const asset of ['preview','pdf']) {
 for(const method of ['GET','HEAD']) {
  calls=[];r=await handle(new Request(url+'&asset='+asset,{method}),deps);
  assert.equal(r.status,404);assert.equal(calls.length,0);
 }
}
r=await handle(new Request(url+'&asset=evil'),deps);assert.equal(r.status,404);
r=await handle(new Request(url,{method:'POST'}),deps);assert.equal(r.status,405);
r=await handle(new Request(url),{env,fetcher:async()=>new Response('secret error',{status:403})});assert.equal(r.status,503);assert.ok(!(await r.text()).includes('secret error'));
r=await handle(new Request(url),{env,fetcher:async()=>{throw new Error('secret');}});assert.equal(r.status,503);
r=await handle(new Request('https://example.org/?health=1'),{env,fetcher:async()=>{throw new Error('Health called DB');}});assert.equal(r.status,200);assert.equal((await r.json()).schema,'hwarang-share-v3');
r=await handle(new Request(url,{method:'HEAD'}),deps);assert.equal(r.status,200);assert.equal(await r.text(),'');
r=await handle(new Request('https://example.org/?health=1'),{env:()=>undefined,fetcher:async()=>{throw new Error('Health called DB');}});assert.equal(r.status,503);
calls=[];r=await handle(new Request(url),{env:n=>n==='SUPABASE_SERVICE_ROLE_KEY'?'sb_secret_synthetic':env(n),fetcher:async(u,o)=>{calls.push(o);return new Response(JSON.stringify(packet));}});assert.equal(r.status,200);assert.equal(calls[0].headers.apikey,'sb_secret_synthetic');assert.ok(!('Authorization' in calls[0].headers));
console.log('Customer HTTP: '+assertions+' assertions passed (HTML, OG, anonymous reads, assets, live closure, no secrets).');
// Render-time badges follow Korea's viewing day; saved prose stays immutable.
const {applyReaderDesign}=await import('../public_reader/worker.js');
const original='<html><head></head><body><p class="meta" data-edition-date="2026-10-26">2026-10-26 브리핑</p><p class="meta" data-edition-date="2026-10-27">2026-10-27 브리핑</p><p class="edition-delay" data-stale-date="2026-10-26" hidden>오늘 브리핑 미제공</p><article><h2>저장된 제목</h2><p>공유 당시 기사와 요약 54.4%</p></article></body></html>';
const updated=applyReaderDesign(original,'2026-10-27');
assert.ok(updated.includes('edition-badge previous">이전 브리핑'));
assert.ok(updated.includes('edition-badge">최신 브리핑'));
assert.ok(updated.includes('<article><h2>저장된 제목</h2><p>공유 당시 기사와 요약 54.4%</p></article>'));
assert.ok(!updated.includes('오늘 브리핑 미제공'));
assert.ok(updated.includes('LINESeedKR-Bd.woff2'));
assert.ok(updated.includes('data-edition-date="2026-10-26"'));
const later=applyReaderDesign(original,'2026-10-28');
assert.equal((later.match(/edition-badge previous">이전 브리핑/g)||[]).length,2);
