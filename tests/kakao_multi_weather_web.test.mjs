import test from 'node:test';import assert from 'node:assert/strict';
import {parseWebWeather,fetchWebWeather,WEB_WEATHER_ENDPOINT} from '../supabase/functions/hwarang-kakao/weather-web.mjs';
import {briefing} from '../supabase/functions/hwarang-kakao/message.mjs';
const now=new Date('2026-10-25T23:00:00Z'),day='2026-10-26';
const doc='<div class="dfs-daily-slide" data-date="2026-10-26"><span title="오전 날씨 구름많음"></span><span title="오후 날씨 비"></span><strong>최저 : </strong><span>11℃</span><strong>최고 : </strong><span>19℃</span></div><div class="dfs-daily-slide" data-date="2026-10-27"><span title="오후 날씨 맑음"></span><strong>최저 : </strong><span>8℃</span></div><dt>단기예보(초단기예보 이후 모레까지):</dt><dd>10.26.(월) 05:00</dd>';
test('existing Workspace parser fixture ports identically and omits HTML/third-party air data',()=>{
 const result=parseWebWeather(doc+'<p>한국환경공단 미세먼지999</p>',{day,now});
 assert.deepEqual(result,{status:'ok',day,low:11,high:19,morning:'구름많음',afternoon:'비',issued_day:day,issued_time:'05:00'});
 const message=briefing(day,[{id:'a',title:'상담'}],false,{...result,region_name:'서울특별시'}).join('\n');assert.ok(message.includes('오전 구름많음 · 오후 비'));assert.ok(!message.includes('시도 대표'));assert.ok(!message.includes('관측 포함 가능'));assert.ok(!message.includes('기상청'));assert.ok(!message.includes('05:00'));assert.ok(!message.includes('강수 0%'));assert.ok(!message.includes('미세먼지'));
});
test('changed structure, wrong day, stale issue and invalid date fail closed',()=>{
 for(const value of [doc.replaceAll('dfs-daily-slide','changed'),doc.replace('10.26.(월) 05:00','10.24.(토) 05:00'),doc.replace('10.26.(월) 05:00','02.30.(월) 05:00'),doc.replaceAll('title="','unknown="')])assert.throws(()=>parseWebWeather(value,{day,now}));
 assert.throws(()=>parseWebWeather(doc,{day:'2026-10-27',now}));
});
test('unknown temperatures remain unknown; injected weather text rejected',()=>{
 assert.equal(parseWebWeather(doc.replace('11℃','-999℃'),{day,now}).low,null);
 assert.throws(()=>parseWebWeather(doc.replace('구름많음','<script>'),{day,now}));
});
test('year boundary accepts recent December issue only',()=>{
 const document=doc.replaceAll('2026-10-26','2027-01-01').replace('10.26.(월) 05:00','12.31.(목) 23:00');
 assert.equal(parseWebWeather(document,{day:'2027-01-01',now:new Date('2026-12-31T15:05:00Z')}).issued_day,'2026-12-31');
});
test('fixed existing endpoint has no key; never fallback on error and no historical fetch',async()=>{
 let calls=0;
 const fetcher=async(url,options)=>{calls++;assert.equal(url.origin+url.pathname,WEB_WEATHER_ENDPOINT);assert.equal(url.searchParams.get('code'),'1100000000');assert.ok(!url.search.includes('Key'));assert.equal(options.redirect,'error');return new Response(doc+'<a href="?dongCode=1100000000#dong/1100000000">x</a>');};
 assert.equal((await fetchWebWeather(fetcher,{day,now,forecast_code:'1100000000'})).high,19);assert.equal(calls,1);
 await assert.rejects(fetchWebWeather(fetcher,{day:'2020-01-01',now,forecast_code:'1100000000'}));assert.equal(calls,1);
 await assert.rejects(fetchWebWeather(async()=>{calls++;throw Error('network');},{day,now,forecast_code:'1100000000'}));assert.equal(calls,2);
});

test('runtime rejects absent or mismatched region echo, never assumes Seoul',()=>{
 assert.throws(()=>parseWebWeather(doc,{day,now,forecast_code:'1100000000'}));
 assert.throws(()=>parseWebWeather(doc+'?dongCode=5100000000#dong/5100000000',{day,now,forecast_code:'1100000000'}));
 assert.equal(parseWebWeather(doc+'?dongCode=1100000000#dong/1100000000',{day,now,forecast_code:'1100000000'}).low,11);
});

test('inline short forecast survives nested tags and is used for the Kakao message',async()=>{
 const inline=doc.split('<dt>')[0]+'초단기예보(현재부터 +6시간까지): <b>10.26.(월) 07:10</b><br />'
  +'단기예보(현재부터 +<span>3</span>일까지): <b>10.26.(월) 05:00</b>'
  +'<script>\n  const dongCode = "1100000000";\n</script>';
 const opts={day,now,forecast_code:'1100000000'};
 const result=await fetchWebWeather(async()=>new Response(inline),opts);
 assert.equal(result.issued_time,'05:00');
 assert.match(briefing(day,[{id:'a',title:'상담'}],false,{...result,region_name:'서울특별시'}).join('\n'),/오후 비/);
 for(const bad of [
  inline.replace('단기예보(현재부터 +<span>3</span>일까지)','중기예보(현재부터 +<span>3</span>일까지)'),
  inline.replace('10.26.(월) 05:00','10.24.(토) 05:00'),
  inline.replace('10.26.(월) 05:00','10.26.(월) 09:00'),
  inline.replaceAll('1100000000','5100000000')+'<a href="?dongCode=1100000000#old">다른 지역 링크</a>',
  inline.replace('단기예보(현재부터 +<span>3</span>일까지): <b>10.26.(월) 05:00</b>','<!-- 단기예보(현재부터 +3일까지): 10.26.(월) 05:00 -->'),
 ])assert.throws(()=>parseWebWeather(bad,opts));
});
