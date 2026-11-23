import test from 'node:test';import assert from 'node:assert/strict';
import {seal,unseal} from '../supabase/functions/hwarang-kakao/crypto.mjs';
import {splitLines,briefing} from '../supabase/functions/hwarang-kakao/message.mjs';
test('encrypted tokens bind owner and generation',async()=>{const secret='x'.repeat(32);const blob=await seal({access_token:'private'},secret,'a',1);assert.equal(blob.includes('private'),false);assert.deepEqual(await unseal(blob,secret,'a',1),{access_token:'private'});await assert.rejects(unseal(blob,secret,'b',1));await assert.rejects(unseal(blob,secret,'a',2));});
test('short message remains single and multiline',()=>assert.deepEqual(splitLines(['오늘 일정','18:00 동호회 · 용산']),['오늘 일정\n18:00 동호회 · 용산']));
test('more than three parts retained losslessly',()=>{const lines=Array.from({length:12},(_,i)=>`${i}:`+'일정'.repeat(70));const parts=splitLines(lines);assert.ok(parts.length>3);assert.ok(parts.every(p=>p.length<=200));assert.equal(parts.join('\n'),lines.join('\n'));});
test('overlong line preserves Unicode without splitting surrogate pairs',()=>{const input='😀'.repeat(300);const parts=splitLines([input]);assert.equal(parts.join(''),input);assert.ok(parts.every(p=>p.length<=200 && !/[\uD800-\uDBFF]$/.test(p)));});
test('events chronological without mutating source',()=>{const rows=[{id:'b',start_time:'19:00',title:'저녁'},{id:'a',start_time:'08:00',title:'아침'}];const text=briefing('2026-11-16',rows)[0];assert.ok(text.indexOf('아침')<text.indexOf('저녁'));assert.equal(rows[0].id,'b');});
test('pending time does not disclose stale start time',()=>{const text=briefing('2026-11-16',[{id:'a',start_time:'08:00',time_pending:true,title:'미정'}])[0];assert.ok(text.includes('시간 미정'));assert.equal(text.includes('08:00'),false)});
test('cancelled status remains visible rather than sounding upcoming',()=>assert.ok(briefing('2026-11-16',[{id:'a',title:'상담',status:'취소'}])[0].includes('[취소]')));

test('weather is appended once without losing long schedules',()=>{
 const rows=Array.from({length:20},(_,i)=>({id:String(i),title:'상담'+i+'가'.repeat(70)}));
 const weather={status:'ok',day:'2026-11-16',region_name:'서울 송파구',low:2,high:10,rain_probability:20,condition:'맑음',issued_day:'2026-11-16',issued_time:'05:00'};
 const parts=briefing('2026-11-16',rows,true,weather),text=parts.join('\n');
 assert.ok(parts.every(p=>p.length<=200));for(const row of rows)assert.ok(text.includes(row.title));
 assert.equal((text.match(/서울 송파구 날씨/g)||[]).length,1);assert.ok(!text.includes('출처:')); assert.ok(text.includes('강수 20%'));
});
test('weather failure does not drop schedule or pretend clear weather',()=>{
 const text=briefing('2026-11-16',[{id:'a',title:'고객 상담'}],false,{status:'unavailable',region_name:'서울 송파구'}).join('\n');
 assert.ok(text.includes('고객 상담'));assert.ok(text.includes('날씨 · 확인하지 못했습니다.'));assert.ok(!text.includes('맑음'));
});
test('wrong-day and invalid weather fail closed',()=>{
 for(const weather of [{status:'ok',day:'2026-11-15'},{status:'ok',day:'2026-11-16',low:100,high:200}])
 assert.ok(briefing('2026-11-16',[],true,weather).join('').includes('확인하지 못했습니다'));
});
test('intentional blank lines improve sections and event spacing',()=>{
 const weather={status:'ok',day:'2026-11-17',region_name:'서울특별시',low:11,high:16,morning:'맑음',afternoon:'흐림',issued_day:'2026-11-17',issued_time:'02:00'};
 const text=briefing('2026-11-17',[{id:'a',start_time:'09:00',title:'상담'},{id:'b',start_time:'11:00',title:'방문'}],false,weather).join('\n');
 assert.ok(text.includes('일정\n\n09:00 상담\n11:00 방문\n\n🌤'));
 assert.ok(text.includes('서울특별시 날씨\n오전'));assert.ok(text.includes('최고 16℃'));assert.ok(!text.includes('시도 대표'));assert.ok(!text.includes('기상청'));assert.ok(!text.includes('02:00'));
});
test('blank boundaries never create empty or oversized parts',()=>{
 for(const lines of [['','','가','','','나','',''],['가'.repeat(198),'','나'],['😀'.repeat(100),'','🌤'],['','']]){
  const parts=splitLines(lines);assert.ok(parts.every(p=>p.trim()&&p.length<=200&&!p.startsWith('\n')&&!p.endsWith('\n')));
  assert.equal(parts.join('').replaceAll('\n',''),lines.join(''));
 }
 assert.deepEqual(splitLines(['가','','','나']),['가\n\n나']);
});

test('common events keep the personal calendar state visible',()=>{
 const shared={id:'s',common:true,title:'지점 회의',start_time:'09:00'};
 for(const [personal,confirmed,label] of [[[],true,'내 일정 없음'],[[],false,'내 일정 미등록'],[[{id:'v',kind:'휴무',title:'휴무'}],false,'오늘은 휴무입니다']]){
  const text=briefing('2026-11-24',[shared,...personal],confirmed).join('\n');
  assert.ok(text.includes(label+'\n\n🏢 지점 공통일정\n09:00 지점 회의'));
 }
 assert.ok(!briefing('2026-11-24',[]).join('').includes('지점 공통일정'));
});
