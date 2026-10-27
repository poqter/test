const {JSDOM}=require('jsdom');const fs=require('fs'),assert=require('assert/strict');
const dir=__dirname+'/../../hwarang_academy/exams/frontend/';
const dom=new JSDOM(fs.readFileSync(dir+'index.html','utf8'),{url:'http://localhost/',runScripts:'outside-only'});const w=dom.window;
let now=0,messages=[],intervals=[],timeouts=[];Object.defineProperty(w.performance,'now',{value:()=>now});w.setInterval=fn=>intervals.push(fn);w.setTimeout=fn=>timeouts.push(fn);w.ResizeObserver=class{observe(){}};w.HTMLElement.prototype.scrollIntoView=function(){};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};w.confirm=()=>true;w.parent.postMessage=m=>messages.push(m);w.eval(fs.readFileSync(dir+'app.js','utf8'));
const base={id:'a',title:'시험',revision:0,status:'active',source_kind:'round',mode:'exam',remaining_seconds:3000,answers:{},flags:[],cursor:0,questions:[1,2,3].map(n=>({number:n,question:'문제 '+n,choices:[{number:1,text:'보기 1'},{number:2,text:'보기 2'}]}))};
let a=structuredClone(base),checks=0;const ok=v=>{assert.ok(v);checks++};const render=(ack=null,error='')=>w.dispatchEvent(new w.MessageEvent('message',{source:w.parent,data:{type:'streamlit:render',args:{attempt:structuredClone(a),ack,error}}}));const last=()=>messages.filter(m=>m.type==='streamlit:setComponentValue').at(-1).value;const el=id=>w.document.getElementById(id);
render();const q=el('question').firstChild,choice=el('choices').firstChild;
now=1100;intervals[0]();ok(el('timer').textContent==='49:59');ok(el('question').firstChild===q);ok(el('choices').firstChild===choice);
choice.click();let req=last();ok(req.action==='save');ok(el('saved').textContent==='저장 중…');ok(el('choices').firstChild===choice);
// Rapid changes remain visible and queue after the in-flight revision.
el('choices').children[1].click();a.answers={'1':1};a.revision=1;render(req.id);req=last();ok(req.payload.answers['1']===2);ok(req.payload.revision===1);a.answers={'1':2};a.revision=2;render(req.id);ok(el('saved').textContent==='저장 완료');ok(el('choices').children[1].getAttribute('aria-pressed')==='true');
// Heartbeat cannot erase user input selected while its reply is in flight.
intervals[1]();req=last();el('choices').firstChild.click();render(req.id);req=last();ok(req.action==='save'&&req.payload.answers['1']===1);a.answers={'1':1};a.revision=3;render(req.id);
// Failure retains selection and retry payload; no false saved message.
el('choices').children[1].click();req=last();render(req.id,'연결 오류');ok(!el('failure').hidden);ok(el('choices').children[1].getAttribute('aria-pressed')==='true');el('retry').click();req=last();a.answers={'1':2};a.revision=4;render(req.id);ok(el('failure').hidden);ok(el('saved').textContent==='저장 완료');
// Navigation and submission use server revision, not client grades.
el('next').click();req=last();ok(req.payload.cursor===1);a.cursor=1;a.revision=5;render(req.id);el('finish').click();ok(el('confirm').open);el('cancel').click();ok(!el('confirm').open);
// A remote revision during a poll cannot be overwritten through retry.
intervals[1]();req=last();el('choices').firstChild.click();a.revision=9;a.answers={'1':2,'2':2};render(req.id);ok(!el('failure').hidden);ok(el('retry').disabled);el('reload').click();req=last();render(req.id);ok(el('failure').hidden);ok(el('choices').children[1].getAttribute('aria-pressed')==='true');
// Expiry locks new answers and asks server to finalize.
now+=3001000;intervals[0]();ok(el('timer').textContent==='00:00');ok([...el('choices').children].every(b=>b.disabled));ok(last().action==='poll');
console.log(JSON.stringify({checks,status:'passed',covers:'DOM stability, timer, queued answers, poll race, retry, navigation, confirmation, expiry'}));dom.window.close();
