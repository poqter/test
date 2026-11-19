import test from 'node:test';
import assert from 'node:assert/strict';
import {briefingBundle} from '../supabase/functions/hwarang-kakao/message.mjs';
import {template} from '../supabase/functions/hwarang-kakao/kakao-api.mjs';
const day='2026-11-20';
const weather={status:'ok',day,region_name:'서울',low:1,high:9,morning:'맑음',afternoon:'흐림',issued_day:day,issued_time:'05:00'};
const summary={identity:{position:'branch_manager'},branch:{name:'드림지점',members:[{name:'김민수',count:3,state:'scheduled'},{name:'박지연',count:2,state:'scheduled'},{name:'휴무직원',count:0,state:'leave'},{name:'없음직원',count:0,state:'empty'},{name:'미등록직원',count:0,state:'missing'}]},events:[{id:'a',title:'지점장 상담',start_time:'09:00',end_time:'10:00'}]};
test('branch first, personal weather second; removed totals stay removed',()=>{
 const parts=briefingBundle(day,summary,weather);assert.equal(parts.length,2);
 assert.equal(parts[0].kind,'branch');assert.equal(parts[1].kind,'personal');
 assert.ok(parts[0].body.includes('11/20(금) 드림지점 일정'));assert.ok(parts[0].body.includes('김민수 3건 · 박지연 2건'));
 assert.ok(parts[0].body.includes('휴무 1명 · 일정 없음 1명\n미등록 1명: 미등록직원'));
 assert.doesNotMatch(parts[0].body,/지점장 상담|날씨|전체|일정 등록|AP/);
 assert.match(parts[1].body,/09:00~10:00 지점장 상담/);assert.match(parts[1].body,/서울 날씨/);
 assert.equal(template(parts[0].body,'https://hwarang-calendar.streamlit.app/calendar','branch').button_title,'오늘 지점 일정 보기');
});
test('overflow preserves every employee before personal parts, max 200 UTF-16',()=>{
 const s=structuredClone(summary);s.branch.members=Array.from({length:60},(_,i)=>({name:'직원'+i+'😀',count:i+1,state:'scheduled'}));
 const parts=briefingBundle(day,s,weather),firstPersonal=parts.findIndex(p=>p.kind==='personal');
 assert.ok(firstPersonal>1);assert.ok(parts.every(p=>p.body.length<=200));assert.ok(parts.slice(firstPersonal).every(p=>p.kind==='personal'));
 const branch=parts.slice(0,firstPersonal).map(p=>p.body).join('\n');for(const m of s.branch.members)assert.ok(branch.includes(m.name+' '+m.count+'건'));
});
test('system admin and team leaders do not gain branch briefing',()=>{
 for(const position of ['team_leader','fp','platform_administrator'])assert.ok(briefingBundle(day,{...summary,identity:{position,role:'super_admin'}},weather).every(p=>p.kind==='personal'));
});

test('leave and work count independently; missing names retain order',()=>{
 const s=structuredClone(summary);s.branch.members[0].on_leave=true;
 const text=briefingBundle(day,s,weather)[0].body;
 assert.ok(text.includes('김민수 3건'));assert.ok(text.includes('휴무 2명'));assert.ok(text.includes('미등록 1명: 미등록직원'));
});
test('many missing names are split without loss under 200 units',()=>{
 const s=structuredClone(summary);s.branch.members=Array.from({length:70},(_,i)=>({name:'미등록직원'+i,count:0,state:'missing'}));
 const parts=briefingBundle(day,s,weather);assert.ok(parts.every(p=>p.body.length<=200));
 const text=parts.filter(p=>p.kind==='branch').map(p=>p.body).join('');
 for(const member of s.branch.members)assert.ok(text.includes(member.name));
});
